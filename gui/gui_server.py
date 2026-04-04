#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import subprocess
import threading
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
    add_subscription,
    delete_node,
    delete_profile,
    delete_subscription,
    ensure_store_initialized,
    get_active_node,
    read_gui_settings,
    refresh_all_subscriptions,
    refresh_subscription,
    save_gui_settings,
    save_manual_import_results,
    save_store,
    store_payload,
    sync_generated_runtime,
    update_node,
    update_profile,
    update_subscription,
)

GUI_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8421
ACTION_LOCK = threading.Lock()
ROOT_GUI_PATHS = ["/", "/index.html"]
REVIEW_GUI_ASSET = "design_review.html"
REVIEW_GUI_PATHS = ["/design-review", "/design-review.html"]
LEGACY_GUI_PATHS = ["/legacy-ui", "/legacy-ui.html", "/classic-ui", "/classic-ui.html"]
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
LAST_ACTION: dict[str, Any] = {
    "name": None,
    "ok": None,
    "message": "GUI готов. Действия выполняются через существующие shell-скрипты.",
    "timestamp": None,
    "details": "",
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


def load_binary_asset(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"Не найден asset: {path}")
    return path.read_bytes()


# Основной web-интерфейс хранится только в одном asset-файле.
INDEX_HTML = load_gui_asset(REVIEW_GUI_ASSET)

@dataclass
class CommandResult:
    name: str
    ok: bool
    returncode: int
    output: str


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def is_pid_alive(value: str | None) -> bool:
    if not value or not value.isdigit():
        return False
    return Path(f"/proc/{value}").exists()


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
) -> dict[str, str]:
    tun_label = tun_interface or "tun0"

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
    LAST_ACTION.update(
        {
            "name": name,
            "ok": ok,
            "message": message,
            "timestamp": iso_now(),
            "details": normalize_output(details),
        }
    )


def run_shell_action(name: str, script: Path, extra_env: dict[str, str] | None = None) -> CommandResult:
    env = os.environ.copy()
    env.update(
        {
            "SUDO_USER": REAL_USER,
            "USER": REAL_USER,
            "LOGNAME": REAL_USER,
            "HOME": str(REAL_HOME),
            "SUBVOST_REAL_XDG_CONFIG_HOME": str(APP_PATHS.config_home),
        }
    )
    env.update(extra_env or {})

    if os.geteuid() != 0:
        command = ["sudo", str(script)]
    else:
        command = [str(script)]

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
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
    active_profile: dict[str, Any] | None,
    active_node: dict[str, Any] | None,
) -> dict[str, Any]:
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
        "generated_path": str(APP_PATHS.generated_xray_config_file),
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


def collect_status() -> dict[str, Any]:
    settings = load_settings()
    store = ensure_store_ready()
    state = load_state_file()
    active_profile, active_node = get_active_node(store)
    runtime_impl = str(state.get("RUNTIME_IMPL") or "xray").strip().lower() or "xray"
    if runtime_impl != "xray":
        runtime_impl = "xray"
    tun_interface = str(state.get("TUN_INTERFACE") or "tun0").strip() or "tun0"
    xray_pid = state.get("XRAY_PID")
    xray_alive = is_pid_alive(xray_pid)
    tun_present = Path("/sys/class/net").joinpath(tun_interface).exists()
    stack_is_live = xray_alive or tun_present
    active_xray_config_path = resolve_active_xray_config_path(store, state, stack_is_live=stack_is_live)
    xray = read_json_config(active_xray_config_path)
    stack_status = describe_stack_status(
        xray_alive=xray_alive,
        tun_present=tun_present,
        tun_interface=tun_interface,
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
        else "Пользовательский backend; возможен запрос sudo в терминале."
    )

    log_files = []
    for candidate in [LOG_DIR / "xray-subvost.log"]:
        if candidate.exists():
            log_files.append(str(candidate))

    store_data = store_payload(store, APP_PATHS)
    runtime_state = describe_runtime_state(
        store,
        state,
        stack_is_live=stack_is_live,
        active_profile=active_profile,
        active_node=active_node,
    )
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
            ],
        },
        "settings": settings,
        "processes": {
            "runtime_impl": runtime_impl,
            "xray_pid": xray_pid if xray_alive else None,
            "xray_alive": xray_alive,
            "tun_present": tun_present,
            "tun_interface": tun_interface,
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
            "requires_terminal_sudo_hint": os.geteuid() != 0,
            "impl": runtime_impl,
            "config_origin": config_origin,
            "active_xray_config": str(active_xray_config_path),
            **runtime_state,
        },
        "artifacts": {
            "latest_diagnostic": str(latest_diag) if latest_diag else None,
            "state_file": str(STATE_FILE),
            "resolv_backup": str(RESOLV_BACKUP),
            "log_files": ", ".join(log_files) if log_files else "Логи ещё не созданы",
            "store_file": str(APP_PATHS.store_file),
            "generated_xray_config": str(APP_PATHS.generated_xray_config_file),
            "active_runtime_xray_config": str(APP_PATHS.active_runtime_xray_config_file),
            "active_xray_config": str(active_xray_config_path),
        },
        "store_summary": store_data["summary"],
        "active_profile": active_profile,
        "active_node": active_node,
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
    store = ensure_store_ready()
    active_profile, active_node = get_active_node(store)
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
    result = run_shell_action("Стоп", STOP_SCRIPT)
    if result.ok:
        message = "Остановка выполнена."
    else:
        message = f"Остановка завершилась ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


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

        if request_path in ROOT_GUI_PATHS or request_path in REVIEW_GUI_PATHS or request_path in LEGACY_GUI_PATHS:
            self.send_html(INDEX_HTML)
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
            "/api/start",
            "/api/stop",
            "/api/diagnostics",
            "/api/import/save",
            "/api/subscriptions/add",
            "/api/subscriptions/refresh",
            "/api/subscriptions/refresh-all",
            "/api/subscriptions/update",
            "/api/subscriptions/delete",
            "/api/selection/activate",
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
        try:
            if self.path == "/api/start":
                response = {"ok": True, "status": handle_start()}
            elif self.path == "/api/stop":
                response = {"ok": True, "status": handle_stop()}
            elif self.path == "/api/diagnostics":
                response = {"ok": True, "status": handle_diagnostics()}
            elif self.path == "/api/import/save":
                response = handle_import_save(payload)
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

    with ThreadingHTTPServer((args.host, args.port), Handler) as httpd:
        print(f"Subvost GUI доступен: http://{args.host}:{args.port}")
        print(f"Корень bundle: {PROJECT_ROOT}")
        print(f"Реальный пользователь: {REAL_USER}")
        print(f"Файл настроек GUI: {APP_PATHS.gui_settings_file}")
        print("Для остановки нажмите Ctrl+C")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
