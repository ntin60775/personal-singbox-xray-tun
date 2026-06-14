"""Инфраструктурные адаптеры — реализация портов RuntimePort, NetworkPort."""
from __future__ import annotations

import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    """Результат выполнения shell-команды."""
    name: str
    ok: bool
    returncode: int
    output: str = ""


@dataclass
class RuntimePort:
    """Порт для операций runtime (start/stop/diagnostics)."""

    def start(self, config_path: Path, asset_dir: Path) -> CommandResult: ...
    def stop(self) -> CommandResult: ...
    def status(self) -> dict[str, Any]: ...


class ShellRuntimeAdapter:
    """RuntimePort через pkexec + subvostd Go-бэкенд.

    Вызывает subvostd --mode {start|stop|diag} напрямую,
    без промежуточных shell-скриптов.
    """

    def __init__(
        self,
        project_root: Path,
        subvostd_path: Path,
        real_uid: int | None = None,
        real_gid: int | None = None,
    ):
        self.project_root = project_root
        self.subvostd_path = subvostd_path
        self.real_uid = real_uid
        self.real_gid = real_gid

    def _run_subvostd(self, name: str, mode: str, extra_env: dict[str, str] | None = None) -> CommandResult:
        """Запустить subvostd --mode <mode> с pkexec или напрямую (если root)."""
        env = os.environ.copy()
        action_env = self._build_action_env(extra_env)
        env.update(action_env)

        if os.geteuid() == 0:
            command = [str(self.subvostd_path), "--mode", mode]
        else:
            pkexec_env = [f"{key}={value}" for key, value in action_env.items()]
            command = ["pkexec", "env", *pkexec_env, str(self.subvostd_path), "--mode", mode]

        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
        except OSError as exc:
            return CommandResult(
                name=name,
                ok=False,
                returncode=127,
                output=f"Не удалось выполнить действие '{name}': {exc}",
            )

        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        ).strip()
        ok = completed.returncode == 0
        return CommandResult(name=name, ok=ok, returncode=completed.returncode, output=output)

    def _build_action_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env: dict[str, str] = {}
        if self.real_uid is not None:
            env["SUDO_UID"] = str(self.real_uid)
        if self.real_gid is not None:
            env["SUDO_GID"] = str(self.real_gid)
        if extra:
            env.update(extra)
        return env

    def start_runtime(self, service):
        """Запустить runtime через pkexec + subvostd --mode start."""
        result = self._run_subvostd("start", "start")
        if not result.ok:
            raise RuntimeError(f"Не удалось запустить подключение: {result.output}")
        return {"ok": True, "output": result.output}

    def stop_runtime(self, service):
        """Остановить runtime через pkexec + subvostd --mode stop."""
        result = self._run_subvostd("stop", "stop")
        if not result.ok:
            raise RuntimeError(f"Не удалось остановить подключение: {result.output}")
        return {"ok": True, "output": result.output}

    def diagnose(self, service):
        """Снять диагностику через pkexec + subvostd --mode diag."""
        result = self._run_subvostd("diagnose", "diag")
        if not result.ok:
            raise RuntimeError(f"Не удалось снять диагностику: {result.output}")
        return {"ok": True, "output": result.output}

class SystemNetworkAdapter:
    """NetworkPort через системные вызовы (/proc, /sys, socket).

    Извлекает системные запросы из SubvostAppService.
    """

    def ping(self, host: str, port: int, timeout: float = 2.0) -> tuple[bool, float | None, str]:
        """TCP-ping узла. Возвращает (успех, задержка_ms, ошибка)."""
        try:
            import time
            start = time.monotonic()
            sock = socket.create_connection((host, port), timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000.0
            sock.close()
            return True, elapsed, ""
        except OSError as e:
            return False, None, str(e)

    def read_resolv_conf_nameservers(self) -> list[str]:
        """Прочитать nameserver-ы из /etc/resolv.conf."""
        servers: list[str] = []
        try:
            for line in Path("/etc/resolv.conf").read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("nameserver"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        except (OSError, PermissionError):
            pass
        return servers

    def read_interface_addresses(self) -> list[dict[str, str]]:
        """Получить адреса сетевых интерфейсов через `ip`."""
        result: list[dict[str, str]] = []
        try:
            output = subprocess.run(
                ["ip", "-brief", "address"],
                capture_output=True, text=True, check=False,
            ).stdout
            for line in output.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3:
                    result.append({
                        "interface": parts[0],
                        "state": parts[1],
                        "addresses": " ".join(parts[2:]),
                    })
        except Exception:
            pass
        return result

    def ping_via_service(self, service, profile_id: str, node_id: str) -> dict[str, Any]:
        """Делегирует пинг узла в SubvostAppService."""
        return service.ping_node_by_id(profile_id, node_id)
