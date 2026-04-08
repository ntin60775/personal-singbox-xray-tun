#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import json
import os
import pwd
import re
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from gui_contract import GUI_VERSION
from subvost_parser import preview_links
from subvost_paths import build_app_paths
from subvost_runtime import node_can_render_runtime, read_json_config
from subvost_store import (
    activate_selection,
    activate_routing_profile,
    add_subscription,
    clear_active_routing_profile,
    delete_node,
    delete_profile,
    delete_subscription,
    ensure_store_initialized,
    get_active_node,
    get_active_routing_profile,
    import_routing_profile,
    read_gui_settings,
    refresh_all_subscriptions,
    refresh_subscription,
    save_gui_settings,
    save_manual_import_results,
    save_store,
    set_routing_enabled,
    store_payload,
    sync_generated_runtime,
    update_node,
    update_profile,
    update_routing_profile_enabled,
    update_subscription,
)

GUI_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8421
ACTION_LOCK = threading.Lock()
ROOT_GUI_PATHS = ["/", "/index.html"]
MAIN_GUI_ASSET = "main_gui.html"
ASSETS_DIR = GUI_DIR.parent / "assets"
FAVICON_ASSET_NAME = "subvost-xray-tun-icon.svg"
FAVICON_PATH = ASSETS_DIR / FAVICON_ASSET_NAME
FAVICON_ROUTE = f"/assets/{FAVICON_ASSET_NAME}"


def discover_project_root() -> Path:
    explicit_root = os.environ.get("SUBVOST_PROJECT_ROOT")
    if explicit_root:
        candidate = Path(explicit_root)
        if not candidate.is_absolute():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT должен быть абсолютным путём: {explicit_root}")
        if not candidate.is_dir():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT не найден: {explicit_root}")
        return candidate

    candidate = GUI_DIR.parent
    if candidate.is_dir():
        return candidate

    raise SystemExit(f"Не удалось определить корень bundle рядом с {GUI_DIR}")


def discover_real_user() -> tuple[str, Path]:
    explicit_user = os.environ.get("SUBVOST_REAL_USER")
    if explicit_user:
        explicit_home = os.environ.get("SUBVOST_REAL_HOME")
        if explicit_home:
            return explicit_user, Path(explicit_home)
        pw_entry = pwd.getpwnam(explicit_user)
        return explicit_user, Path(pw_entry.pw_dir)

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        pw_entry = pwd.getpwnam(sudo_user)
        return sudo_user, Path(pw_entry.pw_dir)

    pkexec_uid = os.environ.get("PKEXEC_UID")
    if pkexec_uid and pkexec_uid.isdigit():
        pw_entry = pwd.getpwuid(int(pkexec_uid))
        return pw_entry.pw_name, Path(pw_entry.pw_dir)

    user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
    pw_entry = pwd.getpwnam(user)
    return user, Path(pw_entry.pw_dir)

def resolve_backend_pid_file(real_uid: int) -> Path:
    explicit_pid_file = os.environ.get("SUBVOST_GUI_BACKEND_PID_FILE")
    if explicit_pid_file:
        candidate = Path(explicit_pid_file)
        if not candidate.is_absolute():
            raise SystemExit(f"SUBVOST_GUI_BACKEND_PID_FILE должен быть абсолютным путём: {explicit_pid_file}")
        return candidate
    return Path(f"/tmp/subvost-xray-tun-gui-user-{real_uid}.pid")

PROJECT_ROOT = discover_project_root()
RUN_SCRIPT = PROJECT_ROOT / "run-xray-tun-subvost.sh"
STOP_SCRIPT = PROJECT_ROOT / "stop-xray-tun-subvost.sh"
DIAG_SCRIPT = PROJECT_ROOT / "capture-xray-tun-state.sh"
LOG_DIR = PROJECT_ROOT / "logs"
XRAY_TEMPLATE_PATH = PROJECT_ROOT / "xray-tun-subvost.json"
REAL_USER, REAL_HOME = discover_real_user()
REAL_PW_ENTRY = pwd.getpwnam(REAL_USER)
REAL_UID = REAL_PW_ENTRY.pw_uid
REAL_GID = REAL_PW_ENTRY.pw_gid
APP_PATHS = build_app_paths(REAL_HOME)
STATE_FILE = REAL_HOME / ".xray-tun-subvost.state"
RESOLV_BACKUP = REAL_HOME / ".xray-tun-subvost.resolv.conf.backup"
GUI_BACKEND_PID_FILE = resolve_backend_pid_file(REAL_UID)
LAST_ACTION: dict[str, Any] = {
    "name": None,
    "ok": None,
    "message": "GUI готов. Действия выполняются через существующие shell-скрипты.",
    "timestamp": None,
    "details": "",
}
ACTION_LOG: deque[dict[str, Any]] = deque(maxlen=200)
PING_CACHE: dict[str, dict[str, Any]] = {}
PING_CACHE_LOCK = threading.Lock()
TRAFFIC_SAMPLE_LOCK = threading.Lock()
LAST_TRAFFIC_SAMPLE: dict[str, Any] = {
    "interface": None,
    "timestamp": None,
    "rx_bytes": None,
    "tx_bytes": None,
}


def runtime_source_label(source: str | None) -> str:
    if source == "store":
        return "Выбранный узел"
    if source == "custom":
        return "Пользовательский config"
    if source == "blocked":
        return "Старт заблокирован"
    return "Не определён"


def load_gui_asset(filename: str) -> str:
    asset_path = GUI_DIR / filename
    if not asset_path.is_file():
        raise FileNotFoundError(f"Не найден GUI asset: {asset_path}")
    return asset_path.read_text(encoding="utf-8")


def load_main_gui_html() -> str:
    return load_gui_asset(MAIN_GUI_ASSET)


def load_binary_asset(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"Не найден asset: {path}")
    return path.read_bytes()


@dataclass
class CommandResult:
    name: str
    ok: bool
    returncode: int
    output: str


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_iso_timestamp(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(candidate).isoformat(timespec="seconds")
    except ValueError:
        return None


def humanize_bytes(value: int | None) -> str:
    if value is None or value < 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    number = float(value)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if number < 1024 or candidate == units[-1]:
            break
        number /= 1024
    decimals = 0 if unit == "B" else 1
    return f"{number:.{decimals}f} {unit}"


def humanize_rate(value: float | None) -> str:
    if value is None or value < 0:
        return "—"
    return f"{humanize_bytes(int(value))}/s"


def log_level_from_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["error", "failed", "traceback", "fatal", "ошибка", "не удалось", "invalid"]):
        return "error"
    if any(token in lowered for token in ["warning", "warn", "предупреж"]):
        return "warning"
    return "info"


def append_action_log_entry(
    *,
    name: str,
    level: str,
    message: str,
    details: str = "",
    source: str = "action",
) -> None:
    ACTION_LOG.append(
        {
            "timestamp": iso_now(),
            "name": name,
            "level": level,
            "message": message,
            "details": normalize_output(details, limit=4000) if details else "",
            "source": source,
        }
    )


def read_interface_byte_counter(interface_name: str, direction: str) -> int | None:
    if not interface_name:
        return None
    counter_path = Path("/sys/class/net") / interface_name / "statistics" / f"{direction}_bytes"
    if not counter_path.exists():
        return None
    try:
        return int(counter_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def collect_traffic_metrics(interface_name: str) -> dict[str, Any]:
    rx_bytes = read_interface_byte_counter(interface_name, "rx")
    tx_bytes = read_interface_byte_counter(interface_name, "tx")
    now = time.monotonic()
    rx_rate = 0.0
    tx_rate = 0.0

    with TRAFFIC_SAMPLE_LOCK:
        previous = LAST_TRAFFIC_SAMPLE.copy()
        LAST_TRAFFIC_SAMPLE.update(
            {
                "interface": interface_name,
                "timestamp": now,
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes,
            }
        )

    if (
        previous.get("interface") == interface_name
        and previous.get("timestamp") is not None
        and rx_bytes is not None
        and tx_bytes is not None
        and previous.get("rx_bytes") is not None
        and previous.get("tx_bytes") is not None
    ):
        elapsed = now - float(previous["timestamp"])
        if elapsed > 0.2:
            rx_delta = max(0, rx_bytes - int(previous["rx_bytes"]))
            tx_delta = max(0, tx_bytes - int(previous["tx_bytes"]))
            rx_rate = rx_delta / elapsed
            tx_rate = tx_delta / elapsed

    available = rx_bytes is not None and tx_bytes is not None
    return {
        "interface": interface_name,
        "available": available,
        "rx_bytes": rx_bytes or 0,
        "tx_bytes": tx_bytes or 0,
        "rx_rate_bytes_per_sec": rx_rate,
        "tx_rate_bytes_per_sec": tx_rate,
        "rx_total_label": humanize_bytes(rx_bytes),
        "tx_total_label": humanize_bytes(tx_bytes),
        "rx_rate_label": humanize_rate(rx_rate if available else None),
        "tx_rate_label": humanize_rate(tx_rate if available else None),
    }


def tail_text_file(path: Path, *, max_bytes: int = 24000) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes), os.SEEK_SET)
        chunk = handle.read()
    return chunk.decode("utf-8", errors="ignore")


def collect_log_payload() -> dict[str, Any]:
    action_entries = list(ACTION_LOG)
    file_entries: list[dict[str, Any]] = []
    log_file = LOG_DIR / "xray-subvost.log"
    tail = tail_text_file(log_file)
    for line in tail.splitlines()[-120:]:
        stripped = line.strip()
        if not stripped:
            continue
        file_entries.append(
            {
                "timestamp": None,
                "name": "xray",
                "level": log_level_from_text(stripped),
                "message": stripped,
                "details": "",
                "source": "file",
            }
        )

    combined = action_entries + file_entries
    latest_error = next((entry for entry in reversed(combined) if entry.get("level") == "error"), None)
    return {
        "entries": combined[-160:],
        "latest_error": latest_error,
        "has_errors": latest_error is not None,
    }


def ping_cache_key(profile_id: str, node_id: str) -> str:
    return f"{profile_id}:{node_id}"


def ping_cache_snapshot() -> dict[str, Any]:
    with PING_CACHE_LOCK:
        return dict(PING_CACHE)


def load_settings() -> dict[str, Any]:
    return read_gui_settings(APP_PATHS, uid=REAL_UID, gid=REAL_GID)


def save_settings(file_logs_enabled: bool) -> None:
    save_gui_settings(APP_PATHS, file_logs_enabled, uid=REAL_UID, gid=REAL_GID)


def load_state_file() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}

    result: dict[str, str] = {}
    for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def normalize_identity_path(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    path = Path(raw)
    if not path.is_absolute():
        return None

    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def state_bundle_project_root(state: dict[str, str]) -> str | None:
    return normalize_identity_path(state.get("BUNDLE_PROJECT_ROOT"))


def classify_runtime_ownership(state: dict[str, str]) -> str:
    bundle_root = state_bundle_project_root(state)
    if not bundle_root:
        return "unknown"

    current_root = normalize_identity_path(str(PROJECT_ROOT)) or str(PROJECT_ROOT)
    return "current" if bundle_root == current_root else "foreign"


def runtime_ownership_label(ownership: str) -> str:
    if ownership == "current":
        return "Текущий bundle"
    if ownership == "foreign":
        return "Другой bundle"
    return "Источник не подтверждён"


def is_pid_alive(value: str | None) -> bool:
    if not value or not value.isdigit():
        return False
    return Path(f"/proc/{value}").exists()


def cleanup_backend_pid_file(pid_file: Path = GUI_BACKEND_PID_FILE, expected_pid: int | None = None) -> bool:
    target_pid = str(expected_pid if expected_pid is not None else os.getpid())
    try:
        recorded_pid = pid_file.read_text(encoding="utf-8").strip()
    except OSError:
        return False

    if recorded_pid != target_pid:
        return False

    try:
        pid_file.unlink()
    except FileNotFoundError:
        return False
    return True


def inspect_runtime_state(state: dict[str, str] | None = None) -> dict[str, Any]:
    runtime_state = load_state_file() if state is None else state
    tun_interface = str(runtime_state.get("TUN_INTERFACE") or "tun0").strip() or "tun0"
    xray_pid = runtime_state.get("XRAY_PID")
    xray_alive = is_pid_alive(xray_pid)
    tun_present = Path("/sys/class/net").joinpath(tun_interface).exists()
    stack_is_live = xray_alive or tun_present
    has_state = bool(runtime_state)
    ownership = classify_runtime_ownership(runtime_state) if has_state else "unknown"
    owned_stack_is_live = ownership == "current" and stack_is_live

    return {
        "state": runtime_state,
        "has_state": has_state,
        "ownership": ownership,
        "ownership_label": runtime_ownership_label(ownership),
        "state_bundle_project_root": state_bundle_project_root(runtime_state),
        "tun_interface": tun_interface,
        "xray_pid": xray_pid,
        "xray_alive": xray_alive,
        "tun_present": tun_present,
        "stack_is_live": stack_is_live,
        "owned_stack_is_live": owned_stack_is_live,
    }


def runtime_control_blocked(runtime_info: dict[str, Any]) -> bool:
    return runtime_info["ownership"] != "current" and (runtime_info["has_state"] or runtime_info["stack_is_live"])


def runtime_control_guard_message(runtime_info: dict[str, Any], *, action: str) -> str:
    state_root = runtime_info.get("state_bundle_project_root")
    tun_interface = runtime_info.get("tun_interface") or "tun0"
    current_root = str(PROJECT_ROOT)

    if runtime_info["ownership"] == "foreign":
        base = (
            f"Обнаружен runtime другого bundle. Bundle-владелец: {state_root}. "
            f"Текущий bundle: {current_root}."
        )
    elif runtime_info["has_state"]:
        base = (
            f"Обнаружен state-файл без bundle identity: {STATE_FILE}. "
            "Для безопасности ownership этого runtime не считается подтверждённым."
        )
    else:
        base = (
            f"Обнаружен активный runtime без подтверждённой bundle identity. "
            f"Интерфейс: {tun_interface}."
        )

    if action == "close":
        return base + " Окно закроется без остановки этого runtime."
    if action == "start":
        return base + " Сначала остановите или проверьте исходный bundle, затем повторите запуск."
    return base + " Текущий bundle не будет управлять этим runtime."


def runtime_stop_required(state: dict[str, str] | None = None) -> bool:
    runtime_info = inspect_runtime_state(state)
    return bool(runtime_info["owned_stack_is_live"])


def read_resolv_conf_nameservers() -> list[str]:
    resolv_path = Path("/etc/resolv.conf")
    if not resolv_path.exists():
        return []

    servers: list[str] = []
    for line in resolv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("nameserver "):
            servers.append(line.split()[1])
    return servers


def read_interface_addresses(interface_name: str) -> str:
    if not interface_name:
        return "—"

    try:
        result = subprocess.run(
            ["ip", "-o", "addr", "show", "dev", interface_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "—"

    addresses: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            addresses.append(parts[3])

    return ", ".join(addresses) if addresses else "—"


def describe_stack_status(
    *,
    xray_alive: bool,
    tun_present: bool,
    tun_interface: str,
    ownership: str,
) -> dict[str, str]:
    tun_label = tun_interface or "tun0"

    if ownership == "foreign" and (xray_alive or tun_present):
        return {
            "state": "degraded",
            "label": "Активен другой bundle",
            "description": f"Обнаружен runtime другой копии bundle. Интерфейс: {tun_label}.",
            "stack_line": "Xray core",
            "stack_subline": "Чужой runtime, управление заблокировано",
        }

    if ownership == "unknown" and (xray_alive or tun_present):
        return {
            "state": "degraded",
            "label": "Ownership не подтверждён",
            "description": f"Обнаружен активный runtime без подтверждённой bundle identity. Интерфейс: {tun_label}.",
            "stack_line": "Xray core",
            "stack_subline": "Источник runtime не подтверждён",
        }

    if xray_alive and tun_present:
        return {
            "state": "running",
            "label": "Подключение активно",
            "description": f"Xray и {tun_label} активны.",
            "stack_line": "Xray core",
            "stack_subline": "Единый TUN-runtime проекта",
        }
    if xray_alive or tun_present:
        return {
            "state": "degraded",
            "label": "Состояние частичное",
            "description": f"Часть runtime активна, стоит снять диагностику. Интерфейс: {tun_label}.",
            "stack_line": "Xray core",
            "stack_subline": "Единый TUN-runtime проекта",
        }
    return {
        "state": "stopped",
        "label": "Runtime остановлен",
        "description": f"Процессы остановлены, {tun_label} не поднят.",
        "stack_line": "Xray core",
        "stack_subline": "Единый TUN-runtime проекта",
    }


def find_latest_diagnostic() -> Path | None:
    if not LOG_DIR.exists():
        return None
    candidates = sorted(LOG_DIR.glob("xray-tun-state-*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def normalize_output(text: str, limit: int = 12000) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "Команда не вернула текстовый вывод."
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def remember_action(name: str, ok: bool | None, message: str, details: str) -> None:
    normalized_details = normalize_output(details)
    LAST_ACTION.update(
        {
            "name": name,
            "ok": ok,
            "message": message,
            "timestamp": iso_now(),
            "details": normalized_details,
        }
    )
    append_action_log_entry(
        name=name,
        level="error" if ok is False else "info",
        message=message,
        details=normalized_details,
    )


def build_shell_action_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    action_env = {
        "SUDO_USER": REAL_USER,
        "USER": REAL_USER,
        "LOGNAME": REAL_USER,
        "HOME": str(REAL_HOME),
        "SUBVOST_PROJECT_ROOT": str(PROJECT_ROOT),
        "SUBVOST_REAL_USER": REAL_USER,
        "SUBVOST_REAL_HOME": str(REAL_HOME),
        "SUBVOST_REAL_XDG_CONFIG_HOME": str(APP_PATHS.config_home),
    }
    action_env.update(extra_env or {})
    return action_env


def build_shell_action_command(script: Path, action_env: dict[str, str]) -> list[str]:
    if os.geteuid() == 0:
        return [str(script)]

    pkexec_env = [f"{key}={value}" for key, value in action_env.items()]
    return ["pkexec", "env", *pkexec_env, "/usr/bin/env", "bash", str(script)]


def run_shell_action(name: str, script: Path, extra_env: dict[str, str] | None = None) -> CommandResult:
    env = os.environ.copy()
    action_env = build_shell_action_env(extra_env)
    env.update(action_env)
    command = build_shell_action_command(script, action_env)

    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
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

    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part).strip()
    ok = completed.returncode == 0
    return CommandResult(name=name, ok=ok, returncode=completed.returncode, output=output)


def ensure_store_ready() -> dict[str, Any]:
    return ensure_store_initialized(APP_PATHS, PROJECT_ROOT, uid=REAL_UID, gid=REAL_GID)


def persist_store(store: dict[str, Any]) -> None:
    save_store(APP_PATHS, store, uid=REAL_UID, gid=REAL_GID)
    sync_generated_runtime(store, APP_PATHS, PROJECT_ROOT, uid=REAL_UID, gid=REAL_GID)


def resolve_active_xray_config_path(
    store: dict[str, Any],
    state: dict[str, str],
    *,
    stack_is_live: bool,
) -> Path:
    state_config = state.get("XRAY_CONFIG")
    if stack_is_live and state_config:
        candidate = Path(state_config)
        if candidate.is_absolute() and candidate.exists():
            return candidate

    return APP_PATHS.generated_xray_config_file


def describe_runtime_state(
    store: dict[str, Any],
    state: dict[str, str],
    *,
    stack_is_live: bool,
    runtime_info: dict[str, Any],
    active_profile: dict[str, Any] | None,
    active_node: dict[str, Any] | None,
) -> dict[str, Any]:
    routing_state = store.get("routing", {})
    active_routing_profile = get_active_routing_profile(store)
    start_ready = bool(
        active_profile
        and active_profile.get("enabled", True)
        and node_can_render_runtime(active_node)
        and APP_PATHS.generated_xray_config_file.exists()
    )

    if start_ready:
        next_start_source = "store"
        next_start_reason = "При следующем старте bundle возьмёт сгенерированный config активного узла."
    else:
        next_start_source = "blocked"
        next_start_reason = "Старт невозможен, пока не выбран и не подготовлен валидный узел."

    if routing_state.get("enabled") and not routing_state.get("runtime_ready"):
        start_ready = False
        next_start_source = "blocked"
        next_start_reason = str(routing_state.get("runtime_error") or "Маршрутизация включена, но не готова.")

    start_blocked = runtime_control_blocked(runtime_info)
    if start_blocked:
        start_ready = False
        next_start_source = "blocked"
        next_start_reason = runtime_control_guard_message(runtime_info, action="start")

    live_source = None
    if stack_is_live:
        live_source = str(state.get("XRAY_CONFIG_SOURCE") or "").strip().lower() or None
        if live_source not in {"store", "custom"}:
            live_source = None

    return {
        "selection_required": True,
        "start_ready": start_ready,
        "live_source": live_source,
        "live_source_label": runtime_source_label(live_source) if live_source else None,
        "next_start_source": next_start_source,
        "next_start_source_label": runtime_source_label(next_start_source),
        "next_start_reason": next_start_reason,
        "ownership": runtime_info["ownership"],
        "ownership_label": runtime_info["ownership_label"],
        "state_bundle_project_root": runtime_info["state_bundle_project_root"],
        "start_blocked": start_blocked,
        "stop_allowed": not start_blocked,
        "control_message": runtime_control_guard_message(runtime_info, action="stop") if start_blocked else "",
        "generated_path": str(APP_PATHS.generated_xray_config_file),
        "routing_enabled": bool(routing_state.get("enabled")),
        "routing_ready": bool(routing_state.get("runtime_ready")),
        "routing_error": str(routing_state.get("runtime_error") or ""),
        "routing_profile_name": active_routing_profile.get("name") if active_routing_profile else "",
    }


def parse_connection_info(
    xray: dict[str, Any],
    active_node: dict[str, Any] | None,
    *,
    tun_interface: str,
) -> dict[str, str]:

    remote_endpoint = "—"
    remote_sni = "—"
    socks_port = "127.0.0.1:10808"
    tun_address = read_interface_addresses(tun_interface)
    protocol_label = "—"
    active_name = active_node.get("name", "—") if active_node else "—"
    active_origin = active_node.get("origin", {}).get("kind", "—") if active_node else "—"

    try:
        proxy = next(outbound for outbound in xray.get("outbounds", []) if outbound.get("tag") == "proxy")
        protocol = str(proxy.get("protocol", "")).strip().lower()
        protocol_label = protocol.upper() if protocol else "—"
        if protocol in {"vless", "vmess"}:
            vnext = proxy.get("settings", {}).get("vnext", [{}])[0]
            address = vnext.get("address")
            port = vnext.get("port")
            if address and port:
                remote_endpoint = f"{address}:{port}"
        elif protocol in {"trojan", "shadowsocks"}:
            server = proxy.get("settings", {}).get("servers", [{}])[0]
            address = server.get("address")
            port = server.get("port")
            if address and port:
                remote_endpoint = f"{address}:{port}"

        stream_settings = proxy.get("streamSettings", {}) or {}
        remote_sni = (
            stream_settings.get("realitySettings", {}).get("serverName")
            or stream_settings.get("tlsSettings", {}).get("serverName")
            or "—"
        )
    except StopIteration:
        pass

    try:
        inbound = next(item for item in xray.get("inbounds", []) if item.get("tag") == "socks-in")
        socks_port = f"{inbound.get('listen', '127.0.0.1')}:{inbound.get('port', 10808)}"
    except StopIteration:
        pass

    dns_servers = []
    for server in xray.get("dns", {}).get("servers", []) or []:
        if isinstance(server, str):
            dns_servers.append(server)
            continue
        address = server.get("address")
        if address:
            dns_servers.append(address)

    return {
        "remote_endpoint": remote_endpoint,
        "remote_sni": remote_sni,
        "local_ports": f"SOCKS {socks_port}",
        "tun_address": tun_address,
        "tun_interface": tun_interface or "tun0",
        "dns_servers": ", ".join(dns_servers) if dns_servers else "—",
        "protocol_label": protocol_label,
        "active_name": active_name,
        "active_origin": active_origin,
    }


def find_profile_and_node(
    store: dict[str, Any],
    profile_id: str,
    node_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for profile in store.get("profiles", []):
        if profile.get("id") != profile_id:
            continue
        for node in profile.get("nodes", []):
            if node.get("id") == node_id:
                return profile, node
        return profile, None
    return None, None


def ping_node(node: dict[str, Any], *, timeout: float = 3.0) -> dict[str, Any]:
    normalized = node.get("normalized", {}) or {}
    host = str(normalized.get("address") or "").strip()
    port = normalized.get("port")
    if not host or not port:
        raise ValueError("Для узла не хватает адреса или порта.")

    started = time.perf_counter()
    with socket.create_connection((host, int(port)), timeout=timeout):
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

    return {
        "host": host,
        "port": int(port),
        "latency_ms": elapsed_ms,
        "label": f"{elapsed_ms:.1f} мс",
        "timestamp": iso_now(),
        "ok": True,
    }


def collect_status() -> dict[str, Any]:
    settings = load_settings()
    store = ensure_store_ready()
    state = load_state_file()
    runtime_info = inspect_runtime_state(state)
    active_profile, active_node = get_active_node(store)
    active_routing_profile = get_active_routing_profile(store)
    routing_state = store.get("routing", {})
    runtime_impl = str(state.get("RUNTIME_IMPL") or "xray").strip().lower() or "xray"
    if runtime_impl != "xray":
        runtime_impl = "xray"
    tun_interface = runtime_info["tun_interface"]
    xray_pid = runtime_info["xray_pid"]
    xray_alive = runtime_info["xray_alive"]
    tun_present = runtime_info["tun_present"]
    stack_is_live = runtime_info["owned_stack_is_live"]
    active_xray_config_path = resolve_active_xray_config_path(store, state, stack_is_live=stack_is_live)
    xray = read_json_config(active_xray_config_path)
    stack_status = describe_stack_status(
        xray_alive=xray_alive,
        tun_present=tun_present,
        tun_interface=tun_interface,
        ownership=runtime_info["ownership"],
    )
    state_key = stack_status["state"]
    state_label = stack_status["label"]
    description = stack_status["description"]

    dns_runtime = ", ".join(read_resolv_conf_nameservers()) or "DNS не прочитан"
    latest_diag = find_latest_diagnostic()
    runtime_mode = "root-server" if os.geteuid() == 0 else "user-server"
    runtime_label = (
        "Root-backend через pkexec."
        if os.geteuid() == 0
        else "Пользовательский backend; root-действия запускаются через pkexec."
    )
    traffic = collect_traffic_metrics(tun_interface)
    logs_payload = collect_log_payload()
    connected_since = normalize_iso_timestamp(state.get("STARTED_AT"))
    if not stack_is_live:
        connected_since = None

    log_files = []
    for candidate in [LOG_DIR / "xray-subvost.log"]:
        if candidate.exists():
            log_files.append(str(candidate))

    store_data = store_payload(store, APP_PATHS)
    runtime_state = describe_runtime_state(
        store,
        state,
        stack_is_live=stack_is_live,
        runtime_info=runtime_info,
        active_profile=active_profile,
        active_node=active_node,
    )
    if routing_state.get("enabled") and active_routing_profile and routing_state.get("runtime_ready"):
        routing_badge = f"маршрут {active_routing_profile.get('name', 'без имени')}"
    elif routing_state.get("enabled"):
        routing_badge = "маршрут с ошибкой"
    elif active_routing_profile:
        routing_badge = f"маршрут {active_routing_profile.get('name', 'без имени')} выключен"
    else:
        routing_badge = "маршрута нет"
    if active_xray_config_path == APP_PATHS.active_runtime_xray_config_file:
        config_origin = "snapshot"
    else:
        config_origin = "generated"

    return {
        "summary": {
            "state": state_key,
            "label": state_label,
            "description": description,
            "stack_line": stack_status["stack_line"],
            "stack_subline": stack_status["stack_subline"],
            "tun_line": f"{tun_interface} готов" if tun_present else f"{tun_interface} отсутствует",
            "dns_line": dns_runtime,
            "logs_line": "Файловые логи включены" if settings["file_logs_enabled"] else "Файловые логи выключены",
            "logs_subline": "Применяется при следующем старте",
            "badges": [
                state_label,
                f"{tun_interface} найден" if tun_present else f"{tun_interface} не найден",
                "логирование включено" if settings["file_logs_enabled"] else "логирование выключено",
                routing_badge,
            ],
        },
        "settings": settings,
        "processes": {
            "runtime_impl": runtime_impl,
            "xray_pid": xray_pid if xray_alive else None,
            "xray_alive": xray_alive,
            "tun_present": tun_present,
            "tun_interface": tun_interface,
            "state_bundle_project_root": runtime_info["state_bundle_project_root"],
            "ownership": runtime_info["ownership"],
        },
        "connection": {
            **parse_connection_info(
                xray,
                active_node,
                tun_interface=tun_interface,
            ),
            "dns_servers": dns_runtime,
        },
        "runtime": {
            "mode": runtime_mode,
            "mode_label": runtime_label,
            "requires_terminal_sudo_hint": False,
            "requires_pkexec_actions": os.geteuid() != 0,
            "impl": runtime_impl,
            "config_origin": config_origin,
            "active_xray_config": str(active_xray_config_path),
            "connected_since": connected_since,
            **runtime_state,
        },
        "traffic": traffic,
        "routing": {
            **routing_state,
            "active_profile": active_routing_profile,
        },
        "ping": {
            "cache": ping_cache_snapshot(),
        },
        "logs": logs_payload,
        "artifacts": {
            "latest_diagnostic": str(latest_diag) if latest_diag else None,
            "state_file": str(STATE_FILE),
            "resolv_backup": str(RESOLV_BACKUP),
            "log_files": ", ".join(log_files) if log_files else "Логи ещё не созданы",
            "store_file": str(APP_PATHS.store_file),
            "generated_xray_config": str(APP_PATHS.generated_xray_config_file),
            "active_runtime_xray_config": str(APP_PATHS.active_runtime_xray_config_file),
            "active_xray_config": str(active_xray_config_path),
            "xray_asset_dir": str(APP_PATHS.xray_asset_dir),
            "geoip_asset_file": str(APP_PATHS.geoip_asset_file),
            "geosite_asset_file": str(APP_PATHS.geosite_asset_file),
        },
        "store_summary": store_data["summary"],
        "active_profile": active_profile,
        "active_node": active_node,
        "active_routing_profile": active_routing_profile,
        "bundle_identity": {
            "project_root": str(PROJECT_ROOT),
            "config_home": str(APP_PATHS.config_home),
        },
        "project_root": str(PROJECT_ROOT),
        "gui_version": GUI_VERSION,
        "last_action": LAST_ACTION.copy(),
        "timestamp": iso_now(),
    }


def handle_start() -> dict[str, Any]:
    runtime_info = inspect_runtime_state()
    if runtime_control_blocked(runtime_info):
        raise ValueError(runtime_control_guard_message(runtime_info, action="start"))
    if runtime_info["owned_stack_is_live"]:
        raise ValueError("Runtime текущего bundle уже активен.")

    store = ensure_store_ready()
    active_profile, active_node = get_active_node(store)
    routing_state = store.get("routing", {})
    if routing_state.get("enabled") and not routing_state.get("runtime_ready"):
        raise ValueError(f"Старт невозможен: {routing_state.get('runtime_error') or 'маршрутизация не готова'}.")
    if not (
        active_profile
        and active_profile.get("enabled", True)
        and node_can_render_runtime(active_node)
        and APP_PATHS.generated_xray_config_file.exists()
    ):
        raise ValueError("Старт невозможен: сначала выбери и активируй валидный узел.")
    settings = load_settings()
    env = {"ENABLE_FILE_LOGS": "1" if settings["file_logs_enabled"] else "0"}
    result = run_shell_action("Старт", RUN_SCRIPT, env)
    if result.ok:
        message = "Запуск завершён успешно."
    else:
        message = f"Запуск завершился ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


def handle_stop() -> dict[str, Any]:
    runtime_info = inspect_runtime_state()
    if runtime_control_blocked(runtime_info):
        raise ValueError(runtime_control_guard_message(runtime_info, action="stop"))
    if not runtime_info["has_state"] and not runtime_info["stack_is_live"]:
        remember_action("Стоп", True, "Остановка не нужна: runtime уже не активен.", "state=already-stopped")
        return collect_status()

    result = run_shell_action("Стоп", STOP_SCRIPT)
    if result.ok:
        message = "Остановка выполнена."
    else:
        message = f"Остановка завершилась ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


def handle_app_terminate(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "window-close").strip() or "window-close"
    runtime_info = inspect_runtime_state()

    if runtime_control_blocked(runtime_info):
        message = runtime_control_guard_message(runtime_info, action="close")
        remember_action("Закрытие приложения", True, message, f"source={source}")
        return {
            "ok": True,
            "message": message,
            "shutdown_source": source,
            "vpn_stop_requested": False,
            "status": collect_status(),
        }

    stop_needed = bool(runtime_info["owned_stack_is_live"])

    if stop_needed:
        result = run_shell_action("Закрытие приложения", STOP_SCRIPT)
        if result.ok:
            message = "Приложение закрывается: VPN runtime остановлен."
        else:
            message = f"Не удалось закрыть приложение: stop runtime завершился ошибкой, код {result.returncode}."
        remember_action(result.name, result.ok, message, result.output)
        if not result.ok:
            raise ValueError(message)
    else:
        message = "Приложение закрывается: VPN runtime уже не активен."
        remember_action("Закрытие приложения", True, message, f"source={source}")

    return {
        "ok": True,
        "message": message,
        "shutdown_source": source,
        "vpn_stop_requested": stop_needed,
        "status": collect_status(),
    }


def handle_gui_shutdown(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "window-close").strip() or "window-close"
    message = "GUI backend закрывается без остановки VPN runtime."
    remember_action("Закрытие GUI", True, message, f"source={source}")
    return {
        "ok": True,
        "message": message,
        "shutdown_source": source,
        "vpn_stop_requested": False,
        "status": collect_status(),
    }


def schedule_server_shutdown(server: ThreadingHTTPServer) -> None:
    def worker() -> None:
        time.sleep(0.1)
        server.shutdown()

    threading.Thread(target=worker, daemon=True).start()


def handle_diagnostics() -> dict[str, Any]:
    result = run_shell_action("Диагностика", DIAG_SCRIPT)
    match = re.search(r"(/.+xray-tun-state-[^\\s]+\\.log)", result.output)
    if result.ok and match:
        message = f"Диагностика сохранена в {match.group(1)}."
    elif result.ok:
        message = "Диагностика снята."
    else:
        message = f"Диагностика завершилась ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


def summarize_previews(results: list[dict[str, Any]]) -> dict[str, int]:
    valid = sum(1 for item in results if item.get("valid"))
    invalid = sum(1 for item in results if not item.get("valid"))
    return {"valid": valid, "invalid": invalid}


def store_response(
    store: dict[str, Any],
    *,
    name: str,
    ok: bool,
    message: str,
    details: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    persist_store(store)
    remember_action(name, ok, message, details)
    payload = {
        "ok": ok,
        "message": message,
        "store": store_payload(store, APP_PATHS),
        "status": collect_status(),
    }
    if extra:
        payload.update(extra)
    return payload


def handle_store_snapshot() -> dict[str, Any]:
    store = ensure_store_ready()
    return {
        "ok": True,
        "store": store_payload(store, APP_PATHS),
        "status": collect_status(),
    }


def handle_import_preview(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", ""))
    results = preview_links(text)
    return {
        "ok": True,
        "results": results,
        "summary": summarize_previews(results),
    }


def handle_import_save(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    text = str(payload.get("text", ""))
    activate_single = bool(payload.get("activate_single"))
    results = preview_links(text)
    summary = summarize_previews(results)
    if summary["valid"] == 0:
        raise ValueError("Нет валидных ссылок для сохранения.")

    save_result = save_manual_import_results(store, results, activate_single=activate_single)
    return store_response(
        store,
        name="Импорт ссылок",
        ok=True,
        message="Импортированные ссылки сохранены в локальный store.",
        details=json.dumps(save_result, ensure_ascii=False),
        extra={"results": results, "summary": save_result},
    )


def handle_routing_import(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    text = str(payload.get("text", ""))
    result = import_routing_profile(store, APP_PATHS, text, uid=REAL_UID, gid=REAL_GID)
    message = (
        f"Routing-профиль '{result['profile']['name']}' "
        f"{'обновлён' if not result['created'] else 'импортирован'}."
    )
    return store_response(
        store,
        name="Импорт маршрутизации",
        ok=True,
        message=message,
        details=json.dumps(
            {
                "routing_profile_id": result["profile"]["id"],
                "created": result["created"],
                "geodata_status": result["geodata"].get("status"),
            },
            ensure_ascii=False,
        ),
        extra={"routing_profile": result["profile"], "routing_import": result},
    )


def handle_routing_activate(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    if not profile_id:
        raise ValueError("Не передан profile_id routing-профиля.")
    profile = activate_routing_profile(store, APP_PATHS, profile_id, uid=REAL_UID, gid=REAL_GID)
    return store_response(
        store,
        name="Активация маршрутизации",
        ok=True,
        message=f"Активным сделан routing-профиль '{profile['name']}'.",
        details=json.dumps({"routing_profile_id": profile_id}, ensure_ascii=False),
        extra={"routing_profile": profile},
    )


def handle_routing_clear_active() -> dict[str, Any]:
    store = ensure_store_ready()
    clear_active_routing_profile(store, APP_PATHS)
    return store_response(
        store,
        name="Сброс маршрутизации",
        ok=True,
        message="Активный routing-профиль снят, маршрутизация выключена.",
        details="routing_active_profile_cleared=1",
    )


def handle_routing_profile_update(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    if not profile_id:
        raise ValueError("Не передан profile_id routing-профиля.")
    if "enabled" not in payload:
        raise ValueError("Не передан флаг enabled для routing-профиля.")
    profile = update_routing_profile_enabled(store, APP_PATHS, profile_id, enabled=bool(payload.get("enabled")))
    return store_response(
        store,
        name="Настройки маршрутизации",
        ok=True,
        message="Состояние routing-профиля сохранено.",
        details=json.dumps({"routing_profile_id": profile_id, "enabled": profile["enabled"]}, ensure_ascii=False),
        extra={"routing_profile": profile},
    )


def handle_routing_toggle(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    if "enabled" not in payload:
        raise ValueError("Не передан флаг enabled для маршрутизации.")
    routing = set_routing_enabled(store, APP_PATHS, bool(payload.get("enabled")), uid=REAL_UID, gid=REAL_GID)
    return store_response(
        store,
        name="Master toggle маршрутизации",
        ok=True,
        message="Маршрутизация включена." if routing["enabled"] else "Маршрутизация выключена.",
        details=json.dumps({"enabled": routing["enabled"]}, ensure_ascii=False),
        extra={"routing": routing},
    )


def handle_subscription_add(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    subscription = add_subscription(store, str(payload.get("name", "")), str(payload.get("url", "")))
    details_payload: dict[str, Any] = {
        "subscription_id": subscription["id"],
        "subscription": subscription,
        "focus_profile_id": subscription["profile_id"],
    }
    try:
        refresh_result = refresh_subscription(store, subscription["id"])
        details_payload["refresh"] = refresh_result
        message = (
            f"Подписка '{subscription['name']}' добавлена. "
            f"Сохранено уникальных узлов: {refresh_result['unique_nodes']}."
        )
    except ValueError as exc:
        try:
            delete_subscription(store, subscription["id"])
        except ValueError:
            pass
        persist_store(store)
        raise ValueError(f"Подписка не добавлена: {exc}.") from exc

    return store_response(
        store,
        name="Добавление подписки",
        ok=True,
        message=message,
        details="\n".join(
            [
                f"subscription_id={subscription['id']}",
                f"profile_id={subscription['profile_id']}",
                f"refresh_status={details_payload.get('refresh', {}).get('status', 'error')}",
                f"valid={details_payload.get('refresh', {}).get('valid', 0)}",
                f"invalid={details_payload.get('refresh', {}).get('invalid', 0)}",
                f"unique_nodes={details_payload.get('refresh', {}).get('unique_nodes', 0)}",
                f"duplicate_lines={details_payload.get('refresh', {}).get('duplicate_lines', 0)}",
            ]
        ),
        extra=details_payload,
    )


def handle_subscription_refresh(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    subscription_id = str(payload.get("subscription_id", "")).strip()
    if not subscription_id:
        raise ValueError("Не передан subscription_id.")
    try:
        result = refresh_subscription(store, subscription_id)
    except ValueError as exc:
        persist_store(store)
        raise ValueError(f"Подписка не обновлена: {exc}. Сохранена предыдущая версия.") from exc
    return store_response(
        store,
        name="Обновление подписки",
        ok=True,
        message=f"Подписка обновлена: сохранено {result['unique_nodes']} уникальных узлов.",
        details=json.dumps(result, ensure_ascii=False),
        extra={"refresh": result},
    )


def handle_subscription_refresh_all() -> dict[str, Any]:
    store = ensure_store_ready()
    result = refresh_all_subscriptions(store)
    ok = result["error"] == 0
    message = "Все включённые подписки обновлены." if ok else "Часть подписок не обновилась."
    return store_response(
        store,
        name="Обновить все подписки",
        ok=ok,
        message=message,
        details=json.dumps(result, ensure_ascii=False),
        extra={"refresh_all": result},
    )


def handle_subscription_update(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    subscription = update_subscription(
        store,
        str(payload.get("subscription_id", "")).strip(),
        name=payload.get("name"),
        enabled=payload.get("enabled"),
    )
    return store_response(
        store,
        name="Настройки подписки",
        ok=True,
        message="Настройки подписки сохранены.",
        details=json.dumps({"subscription_id": subscription["id"]}, ensure_ascii=False),
        extra={"subscription": subscription},
    )


def handle_subscription_delete(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    subscription_id = str(payload.get("subscription_id", "")).strip()
    if not subscription_id:
        raise ValueError("Не передан subscription_id.")
    delete_subscription(store, subscription_id)
    return store_response(
        store,
        name="Удаление подписки",
        ok=True,
        message="Подписка и связанный профиль удалены.",
        details=json.dumps({"subscription_id": subscription_id}, ensure_ascii=False),
    )

def handle_selection_activate(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    node_id = str(payload.get("node_id", "")).strip()
    if not profile_id or not node_id:
        raise ValueError("Для активации нужны profile_id и node_id.")
    node = activate_selection(store, profile_id, node_id)
    return store_response(
        store,
        name="Активация узла",
        ok=True,
        message=f"Активным сделан узел '{node['name']}'.",
        details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
        extra={"node": node},
    )


def handle_profile_update(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile = update_profile(
        store,
        str(payload.get("profile_id", "")).strip(),
        name=payload.get("name"),
        enabled=payload.get("enabled"),
    )
    return store_response(
        store,
        name="Настройки профиля",
        ok=True,
        message="Профиль обновлён.",
        details=json.dumps({"profile_id": profile["id"]}, ensure_ascii=False),
        extra={"profile": profile},
    )


def handle_profile_delete(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    if not profile_id:
        raise ValueError("Не передан profile_id.")
    delete_profile(store, profile_id)
    return store_response(
        store,
        name="Удаление профиля",
        ok=True,
        message="Профиль удалён.",
        details=json.dumps({"profile_id": profile_id}, ensure_ascii=False),
    )


def handle_node_update(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    node_id = str(payload.get("node_id", "")).strip()
    if not profile_id or not node_id:
        raise ValueError("Для изменения узла нужны profile_id и node_id.")
    node = update_node(
        store,
        profile_id,
        node_id,
        name=payload.get("name"),
        enabled=payload.get("enabled"),
    )
    return store_response(
        store,
        name="Настройки узла",
        ok=True,
        message="Узел обновлён.",
        details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
        extra={"node": node},
    )


def handle_node_delete(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    node_id = str(payload.get("node_id", "")).strip()
    if not profile_id or not node_id:
        raise ValueError("Для удаления узла нужны profile_id и node_id.")
    delete_node(store, profile_id, node_id)
    return store_response(
        store,
        name="Удаление узла",
        ok=True,
        message="Узел удалён.",
        details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
    )


def handle_node_ping(payload: dict[str, Any]) -> dict[str, Any]:
    store = ensure_store_ready()
    profile_id = str(payload.get("profile_id", "")).strip()
    node_id = str(payload.get("node_id", "")).strip()
    if not profile_id or not node_id:
        raise ValueError("Для ping нужны profile_id и node_id.")

    profile, node = find_profile_and_node(store, profile_id, node_id)
    if not profile or not node:
        raise ValueError("Узел для ping не найден.")
    if not profile.get("enabled", True):
        raise ValueError("Профиль отключён.")
    if not node.get("enabled", True):
        raise ValueError("Узел отключён.")

    try:
        result = ping_node(node)
    except OSError as exc:
        message = f"Ping не выполнен: {exc}."
        result = {
            "host": str(node.get("normalized", {}).get("address") or "—"),
            "port": node.get("normalized", {}).get("port"),
            "latency_ms": None,
            "label": "Ошибка",
            "timestamp": iso_now(),
            "ok": False,
            "error": str(exc),
        }
        with PING_CACHE_LOCK:
            PING_CACHE[ping_cache_key(profile_id, node_id)] = result
        raise ValueError(message) from exc

    with PING_CACHE_LOCK:
        PING_CACHE[ping_cache_key(profile_id, node_id)] = result

    remember_action(
        "Ping узла",
        True,
        f"Узел '{node.get('name', 'без имени')}' ответил за {result['label']}.",
        json.dumps(
            {
                "profile_id": profile_id,
                "node_id": node_id,
                **result,
            },
            ensure_ascii=False,
        ),
    )
    return {
        "ok": True,
        "ping": {
            "profile_id": profile_id,
            "node_id": node_id,
            **result,
        },
        "status": collect_status(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SubvostGui/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, payload: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(payload)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        request_path = self.path.split("?", 1)[0]

        if request_path in {"/favicon.ico", FAVICON_ROUTE}:
            self.send_bytes(load_binary_asset(FAVICON_PATH), "image/svg+xml; charset=utf-8")
            return

        if request_path in ROOT_GUI_PATHS:
            self.send_html(load_main_gui_html())
            return

        if request_path == "/api/status":
            self.send_json(collect_status())
            return

        if request_path == "/api/store":
            self.send_json(handle_store_snapshot())
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path == "/api/settings/logging":
            payload = self.read_json_body()
            enabled = bool(payload.get("enabled"))
            save_settings(enabled)
            remember_action(
                "Настройки",
                True,
                "Режим файлового логирования сохранён.",
                f"file_logs_enabled={int(enabled)}",
            )
            self.send_json({"ok": True, "status": collect_status()})
            return

        if self.path == "/api/import/preview":
            self.send_json(handle_import_preview(self.read_json_body()))
            return

        if self.path not in [
            "/api/app/terminate",
            "/api/app/shutdown-gui",
            "/api/start",
            "/api/stop",
            "/api/diagnostics",
            "/api/import/save",
            "/api/routing/import",
            "/api/routing/activate",
            "/api/routing/clear-active",
            "/api/routing/profile/update",
            "/api/routing/toggle",
            "/api/subscriptions/add",
            "/api/subscriptions/refresh",
            "/api/subscriptions/refresh-all",
            "/api/subscriptions/update",
            "/api/subscriptions/delete",
            "/api/selection/activate",
            "/api/nodes/ping",
            "/api/profiles/update",
            "/api/profiles/delete",
            "/api/nodes/update",
            "/api/nodes/delete",
        ]:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        if not ACTION_LOCK.acquire(blocking=False):
            self.send_json(
                {
                    "ok": False,
                    "message": "Другая операция ещё выполняется. Дождитесь завершения.",
                    "status": collect_status(),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        payload = self.read_json_body()
        shutdown_after_response = False
        try:
            if self.path == "/api/app/terminate":
                response = handle_app_terminate(payload)
                shutdown_after_response = True
            elif self.path == "/api/app/shutdown-gui":
                response = handle_gui_shutdown(payload)
                shutdown_after_response = True
            elif self.path == "/api/start":
                response = {"ok": True, "status": handle_start()}
            elif self.path == "/api/stop":
                response = {"ok": True, "status": handle_stop()}
            elif self.path == "/api/diagnostics":
                response = {"ok": True, "status": handle_diagnostics()}
            elif self.path == "/api/import/save":
                response = handle_import_save(payload)
            elif self.path == "/api/routing/import":
                response = handle_routing_import(payload)
            elif self.path == "/api/routing/activate":
                response = handle_routing_activate(payload)
            elif self.path == "/api/routing/clear-active":
                response = handle_routing_clear_active()
            elif self.path == "/api/routing/profile/update":
                response = handle_routing_profile_update(payload)
            elif self.path == "/api/routing/toggle":
                response = handle_routing_toggle(payload)
            elif self.path == "/api/subscriptions/add":
                response = handle_subscription_add(payload)
            elif self.path == "/api/subscriptions/refresh":
                response = handle_subscription_refresh(payload)
            elif self.path == "/api/subscriptions/refresh-all":
                response = handle_subscription_refresh_all()
            elif self.path == "/api/subscriptions/update":
                response = handle_subscription_update(payload)
            elif self.path == "/api/subscriptions/delete":
                response = handle_subscription_delete(payload)
            elif self.path == "/api/selection/activate":
                response = handle_selection_activate(payload)
            elif self.path == "/api/nodes/ping":
                response = handle_node_ping(payload)
            elif self.path == "/api/profiles/update":
                response = handle_profile_update(payload)
            elif self.path == "/api/profiles/delete":
                response = handle_profile_delete(payload)
            elif self.path == "/api/nodes/update":
                response = handle_node_update(payload)
            else:
                response = handle_node_delete(payload)
        except ValueError as exc:
            remember_action("Ошибка операции", False, str(exc), str(exc))
            self.send_json(
                {
                    "ok": False,
                    "message": str(exc),
                    "status": collect_status(),
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        finally:
            ACTION_LOCK.release()

        self.send_json(response)
        if shutdown_after_response:
            schedule_server_shutdown(self.server)


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальный GUI для управления Subvost Xray TUN bundle.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Адрес для HTTP сервера. По умолчанию {DEFAULT_HOST}.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Порт для HTTP сервера. По умолчанию {DEFAULT_PORT}.")
    args = parser.parse_args()

    remember_action(
        "Инициализация",
        True,
        f"GUI backend запущен для пользователя {REAL_USER}. Откройте http://{args.host}:{args.port}",
        "Сервер готов к работе.",
    )
    atexit.register(cleanup_backend_pid_file)

    with ThreadingHTTPServer((args.host, args.port), Handler) as httpd:
        print(f"Subvost GUI доступен: http://{args.host}:{args.port}")
        print(f"Корень bundle: {PROJECT_ROOT}")
        print(f"Реальный пользователь: {REAL_USER}")
        print(f"Файл настроек GUI: {APP_PATHS.gui_settings_file}")
        print("Для остановки нажмите Ctrl+C")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
