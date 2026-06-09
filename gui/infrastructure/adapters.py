"""Инфраструктурные адаптеры — реализация портов RuntimePort, NetworkPort."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Обеспечиваем плоский импорт из gui/
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


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
    """RuntimePort через pkexec + shell-скрипты.

    Извлекает shell-оркестрацию из SubvostAppService.
    Делегирует тяжелые операции shell-скриптам через subprocess.
    """

    def __init__(
        self,
        project_root: Path,
        libexec_dir: Path,
        real_uid: int | None = None,
        real_gid: int | None = None,
    ):
        self.project_root = project_root
        self.libexec_dir = libexec_dir
        self.real_uid = real_uid
        self.real_gid = real_gid

    def run_script(self, name: str, script: Path, extra_env: dict[str, str] | None = None) -> CommandResult:
        """Запустить shell-скрипт с pkexec или напрямую (если root)."""
        env = os.environ.copy()
        action_env = self._build_action_env(extra_env)
        env.update(action_env)
        command = self._build_command(script, action_env)

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

    def _build_command(self, script: Path, action_env: dict[str, str]) -> list[str]:
        if os.geteuid() == 0:
            return [str(script)]
        pkexec_env = [f"{key}={value}" for key, value in action_env.items()]
        return ["pkexec", "env", *pkexec_env, "/usr/bin/env", "bash", str(script)]


    def start_runtime(self, service):
        """Делегирует запуск runtime в SubvostAppService."""
        return service.start_runtime()

    def stop_runtime(self, service):
        """Делегирует остановку runtime в SubvostAppService."""
        return service.stop_runtime()

    def diagnose(self, service):
        """Делегирует снятие диагностики в SubvostAppService."""
        return service.capture_diagnostics()

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
