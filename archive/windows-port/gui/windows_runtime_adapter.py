from __future__ import annotations

import copy
import ipaddress
import json
import locale
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from subvost_paths import atomic_write_json, read_json_file
from subvost_runtime import find_proxy_outbound


WINDOWS_TUN_ADAPTER = "SubvostTun"
HOST_ROUTE_MASK = "255.255.255.255"


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class RoutePlan:
    proxy_host: str
    proxy_ips: list[str]
    gateway: str
    interface: str
    add_commands: list[list[str]]
    delete_commands: list[list[str]]


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def decode_command_output(payload: bytes) -> str:
    if not payload:
        return ""
    candidates = [
        "utf-8",
        locale.getpreferredencoding(False),
        "cp866",
        "cp1251",
        "mbcs",
    ]
    seen: set[str] = set()
    for encoding in candidates:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


class WindowsCommandRunner:
    def run(self, args: Iterable[str], *, cwd: Path | None = None, timeout: int = 20) -> CommandResult:
        command = [str(item) for item in args]
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return CommandResult(
            args=command,
            returncode=completed.returncode,
            stdout=decode_command_output(completed.stdout),
            stderr=decode_command_output(completed.stderr),
        )


def parse_ipv4_default_gateway(route_print_output: str) -> tuple[str, str]:
    for line in route_print_output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[0] != "0.0.0.0" or parts[1] != "0.0.0.0":
            continue
        gateway = parts[2]
        interface = parts[3]
        if gateway.lower() == "on-link":
            continue
        try:
            ipaddress.IPv4Address(gateway)
            ipaddress.IPv4Address(interface)
        except ValueError:
            continue
        return gateway, interface
    raise ValueError("Не найден IPv4 default gateway в выводе `route print`.")


def normalize_proxy_ips(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        try:
            ip = str(ipaddress.IPv4Address(value))
        except ValueError:
            continue
        if ip not in result:
            result.append(ip)
    return result


def resolve_ipv4_addresses(host: str) -> list[str]:
    try:
        ipaddress.IPv4Address(host)
        return [host]
    except ValueError:
        pass

    addresses: list[str] = []
    for family, _socktype, _proto, _canonname, sockaddr in socket.getaddrinfo(host, None, socket.AF_INET):
        if family == socket.AF_INET:
            addresses.append(str(sockaddr[0]))
    return normalize_proxy_ips(addresses)


def proxy_endpoint_from_config(config: dict[str, Any]) -> tuple[str, int | None]:
    outbound = find_proxy_outbound(config)
    if not outbound:
        raise ValueError("В активном Xray-конфиге не найден outbound `proxy`.")
    protocol = str(outbound.get("protocol") or "").lower()
    if protocol in {"vless", "vmess"}:
        vnext = outbound.get("settings", {}).get("vnext", [{}])[0]
        return str(vnext.get("address") or "").strip(), vnext.get("port")
    if protocol in {"trojan", "shadowsocks"}:
        server = outbound.get("settings", {}).get("servers", [{}])[0]
        return str(server.get("address") or "").strip(), server.get("port")
    raise ValueError(f"Неподдерживаемый protocol для Windows runtime: {protocol}")


def remove_linux_sockopt(stream_settings: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(stream_settings)
    sockopt = copy.deepcopy(updated.get("sockopt") or {})
    sockopt.pop("mark", None)
    sockopt.pop("interface", None)
    if sockopt:
        updated["sockopt"] = sockopt
    else:
        updated.pop("sockopt", None)
    return updated


def prepare_windows_xray_config(config: dict[str, Any], *, adapter_name: str = WINDOWS_TUN_ADAPTER) -> dict[str, Any]:
    prepared = copy.deepcopy(config)
    for inbound in prepared.get("inbounds", []):
        if inbound.get("protocol") != "tun":
            continue
        settings = copy.deepcopy(inbound.get("settings") or {})
        settings["name"] = adapter_name
        inbound["settings"] = settings

    for outbound in prepared.get("outbounds", []):
        stream_settings = outbound.get("streamSettings")
        if isinstance(stream_settings, dict):
            outbound["streamSettings"] = remove_linux_sockopt(stream_settings)
    return prepared


class WindowsRuntimeController:
    def __init__(
        self,
        *,
        project_root: Path,
        config_path: Path,
        active_config_path: Path,
        runtime_dir: Path,
        state_file: Path,
        log_dir: Path,
        diagnostic_dir: Path,
        runner: WindowsCommandRunner | None = None,
        popen_factory: Callable[..., Any] | None = None,
        resolver: Callable[[str], list[str]] = resolve_ipv4_addresses,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_root = project_root
        self.config_path = config_path
        self.active_config_path = active_config_path
        self.runtime_dir = runtime_dir
        self.state_file = state_file
        self.log_dir = log_dir
        self.diagnostic_dir = diagnostic_dir
        self.runner = runner or WindowsCommandRunner()
        self.popen_factory = popen_factory or subprocess.Popen
        self.resolver = resolver
        self.sleep = sleep

    @property
    def xray_exe(self) -> Path:
        return self.runtime_dir / "xray.exe"

    @property
    def wintun_dll(self) -> Path:
        return self.runtime_dir / "wintun.dll"

    def read_state(self) -> dict[str, Any]:
        return read_json_file(self.state_file)

    def write_state(self, payload: dict[str, Any]) -> None:
        atomic_write_json(self.state_file, payload)

    def assert_runtime_files(self) -> None:
        missing = [str(path) for path in [self.xray_exe, self.wintun_dll, self.config_path] if not path.exists()]
        if missing:
            raise ValueError("Не найдены runtime-файлы Windows: " + ", ".join(missing))

    def load_prepared_config(self) -> tuple[dict[str, Any], str, list[str]]:
        config = read_json_file(self.config_path)
        if not config:
            raise ValueError(f"Активный Xray-конфиг не найден или пуст: {self.config_path}")
        proxy_host, _proxy_port = proxy_endpoint_from_config(config)
        if not proxy_host:
            raise ValueError("В активном узле не найден proxy endpoint.")
        proxy_ips = self.resolver(proxy_host)
        if not proxy_ips:
            raise ValueError(f"Не удалось определить IPv4 адрес proxy endpoint: {proxy_host}")
        prepared = prepare_windows_xray_config(config)
        atomic_write_json(self.active_config_path, prepared)
        return prepared, proxy_host, proxy_ips

    def build_route_plan(self, proxy_host: str, proxy_ips: list[str]) -> RoutePlan:
        route_print = self.runner.run(["route", "print", "0.0.0.0"])
        if not route_print.ok:
            raise ValueError(f"Не удалось прочитать таблицу маршрутов: {route_print.stderr or route_print.stdout}")
        gateway, interface = parse_ipv4_default_gateway(route_print.stdout)
        normalized_ips = normalize_proxy_ips(proxy_ips)
        if not normalized_ips:
            raise ValueError(f"Не найден IPv4 адрес proxy endpoint: {proxy_host}")
        add_commands = [["route", "ADD", ip, "MASK", HOST_ROUTE_MASK, gateway, "METRIC", "1"] for ip in normalized_ips]
        delete_commands = [["route", "DELETE", ip, "MASK", HOST_ROUTE_MASK] for ip in normalized_ips]
        return RoutePlan(
            proxy_host=proxy_host,
            proxy_ips=normalized_ips,
            gateway=gateway,
            interface=interface,
            add_commands=add_commands,
            delete_commands=delete_commands,
        )

    def apply_route_plan(self, plan: RoutePlan) -> list[CommandResult]:
        applied: list[CommandResult] = []
        for command in plan.add_commands:
            result = self.runner.run(command)
            applied.append(result)
            if not result.ok:
                self.rollback_routes(plan, only=applied)
                raise ValueError(f"Не удалось добавить host route к proxy endpoint: {result.stderr or result.stdout}")
        return applied

    def rollback_routes(self, plan: RoutePlan, *, only: list[CommandResult] | None = None) -> list[CommandResult]:
        commands = plan.delete_commands
        if only is not None:
            added_ips = {result.args[2] for result in only if len(result.args) > 2 and result.ok}
            commands = [command for command in plan.delete_commands if len(command) > 2 and command[2] in added_ips]
        results = []
        for command in commands:
            results.append(self.runner.run(command))
        return results

    def process_is_alive(self, process: Any) -> bool:
        poll = getattr(process, "poll", None)
        if callable(poll):
            return poll() is None
        return True

    def start_process(self) -> Any:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / "xray-windows-runtime.log"
        log_handle = log_path.open("ab")
        try:
            return self.popen_factory(
                [str(self.xray_exe), "run", "-c", str(self.active_config_path)],
                cwd=str(self.project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                close_fds=True,
            )
        finally:
            log_handle.close()

    def check_adapter(self) -> CommandResult:
        return self.runner.run(["netsh", "interface", "show", "interface", f"name={WINDOWS_TUN_ADAPTER}"])

    def start(self) -> dict[str, Any]:
        self.assert_runtime_files()
        _prepared, proxy_host, proxy_ips = self.load_prepared_config()
        plan = self.build_route_plan(proxy_host, proxy_ips)
        applied_routes = self.apply_route_plan(plan)
        process = None
        try:
            process = self.start_process()
            self.sleep(1.0)
            if not self.process_is_alive(process):
                raise ValueError("Xray process завершился сразу после старта.")
            adapter_result = self.check_adapter()
            if not adapter_result.ok:
                raise ValueError(f"Не найден адаптер {WINDOWS_TUN_ADAPTER}: {adapter_result.stderr or adapter_result.stdout}")
        except Exception:
            if process is not None:
                terminate = getattr(process, "terminate", None)
                if callable(terminate):
                    terminate()
            self.rollback_routes(plan, only=applied_routes)
            raise

        state = {
            "schema": 1,
            "state": "running",
            "started_at": iso_now(),
            "xray_pid": getattr(process, "pid", None),
            "adapter": WINDOWS_TUN_ADAPTER,
            "active_config": str(self.active_config_path),
            "runtime_dir": str(self.runtime_dir),
            "proxy_host": plan.proxy_host,
            "proxy_ips": plan.proxy_ips,
            "gateway": plan.gateway,
            "interface": plan.interface,
            "route_delete_commands": plan.delete_commands,
            "log_file": str(self.log_dir / "xray-windows-runtime.log"),
        }
        self.write_state(state)
        return state

    def stop(self) -> dict[str, Any]:
        state = self.read_state()
        route_delete_commands = state.get("route_delete_commands") or []
        route_results = []
        for command in route_delete_commands:
            if isinstance(command, list) and command:
                route_results.append(self.runner.run([str(item) for item in command]))

        pid = state.get("xray_pid")
        kill_result = None
        if pid:
            kill_result = self.runner.run(["taskkill", "/PID", str(pid), "/T", "/F"])

        stopped_state = {
            **state,
            "state": "stopped",
            "stopped_at": iso_now(),
            "route_cleanup": [result.__dict__ for result in route_results],
            "process_cleanup": kill_result.__dict__ if kill_result else None,
        }
        self.write_state(stopped_state)
        return stopped_state

    def inspect(self) -> dict[str, Any]:
        state = self.read_state()
        return {
            "state": state.get("state") or "stopped",
            "xray_pid": state.get("xray_pid"),
            "adapter": state.get("adapter") or WINDOWS_TUN_ADAPTER,
            "started_at": state.get("started_at"),
            "stopped_at": state.get("stopped_at"),
            "proxy_host": state.get("proxy_host"),
            "proxy_ips": state.get("proxy_ips") or [],
            "gateway": state.get("gateway"),
            "state_file": str(self.state_file),
            "log_file": state.get("log_file") or str(self.log_dir / "xray-windows-runtime.log"),
            "route_delete_commands": state.get("route_delete_commands") or [],
        }

    def capture_diagnostics(self) -> dict[str, Any]:
        self.diagnostic_dir.mkdir(parents=True, exist_ok=True)
        commands = {
            "route_print": ["route", "print"],
            "netsh_interfaces": ["netsh", "interface", "show", "interface"],
            "ipconfig": ["ipconfig", "/all"],
            "tasklist_xray": ["tasklist", "/FI", "IMAGENAME eq xray.exe"],
        }
        command_results: dict[str, Any] = {}
        for key, command in commands.items():
            result = self.runner.run(command)
            command_results[key] = result.__dict__

        state = self.inspect()
        recovery_commands = [" ".join(command) for command in state.get("route_delete_commands", []) if isinstance(command, list)]
        diagnostic = {
            "schema": 1,
            "created_at": iso_now(),
            "state": state,
            "commands": command_results,
            "recovery": {
                "route_delete_commands": recovery_commands,
                "stop_process_command": f"taskkill /PID {state['xray_pid']} /T /F" if state.get("xray_pid") else "",
            },
        }
        path = self.diagnostic_dir / f"subvost-win81-diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"path": str(path), "diagnostic": diagnostic}
