from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gui_contract import GUI_VERSION
from subvost_paths import AppPaths, build_app_paths, read_json_file
from subvost_routing import build_direct_routes_report
from subvost_runtime import read_json_config
from subvost_store import (
    activate_selection as store_activate_selection,
    add_subscription as store_add_subscription,
    ensure_store_initialized,
    get_active_node,
    refresh_all_subscriptions as store_refresh_all_subscriptions,
    refresh_subscription as store_refresh_subscription,
    save_store,
    store_payload,
    sync_generated_runtime,
)
from windows_runtime_adapter import WINDOWS_TUN_ADAPTER, WindowsRuntimeController


@dataclass(frozen=True)
class WindowsCoreContext:
    project_root: Path
    real_home: Path
    local_app_data: Path
    app_paths: AppPaths
    log_dir: Path
    runtime_state_file: Path
    diagnostic_dir: Path
    runtime_dir: Path


class CommandError(Exception):
    def __init__(self, message: str, *, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.data = data or {}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_project_root() -> Path:
    explicit_root = os.environ.get("SUBVOST_PROJECT_ROOT", "").strip()
    if explicit_root:
        candidate = Path(explicit_root)
        if not candidate.is_absolute():
            raise CommandError(f"SUBVOST_PROJECT_ROOT должен быть абсолютным путём: {explicit_root}")
        if not candidate.is_dir():
            raise CommandError(f"SUBVOST_PROJECT_ROOT не найден: {explicit_root}")
        return candidate
    return repo_root_from_script()


def resolve_windows_home() -> Path:
    for env_name in ("SUBVOST_WINDOWS_HOME", "USERPROFILE", "HOME"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value)
    return Path.home()


def resolve_local_app_data(real_home: Path) -> Path:
    for env_name in ("SUBVOST_WINDOWS_LOCALAPPDATA", "LOCALAPPDATA"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value)
    return real_home / "AppData" / "Local"


def build_context() -> WindowsCoreContext:
    project_root = resolve_project_root()
    real_home = resolve_windows_home()
    local_app_data = resolve_local_app_data(real_home)
    app_paths = build_app_paths(real_home, str(local_app_data))
    log_dir = Path(os.environ.get("SUBVOST_WINDOWS_LOG_DIR", "") or app_paths.store_dir / "logs")
    runtime_state_file = app_paths.store_dir / "windows-runtime-state.json"
    diagnostic_dir = log_dir / "diagnostics"
    runtime_dir = project_root / "runtime"
    return WindowsCoreContext(
        project_root=project_root,
        real_home=real_home,
        local_app_data=local_app_data,
        app_paths=app_paths,
        log_dir=log_dir,
        runtime_state_file=runtime_state_file,
        diagnostic_dir=diagnostic_dir,
        runtime_dir=runtime_dir,
    )


def write_json_stdout(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def command_name(argv: list[str]) -> str:
    return " ".join(item for item in argv if item != "--json") or "status"


def envelope(
    *,
    ok: bool,
    command: str,
    message: str,
    data: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
    store: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "command": command,
        "message": message,
        "data": data or {},
        "status": status or {},
        "store": store or {},
        "error": error,
        "version": GUI_VERSION,
        "timestamp": iso_now(),
    }


def flatten_nodes(store: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    active_profile, active_node = get_active_node(store)
    active_profile_id = active_profile.get("id") if active_profile else None
    active_node_id = active_node.get("id") if active_node else None
    for profile in store.get("profiles", []):
        profile_id = str(profile.get("id") or "")
        for node in profile.get("nodes", []):
            normalized = node.get("normalized") or {}
            nodes.append(
                {
                    "profile_id": profile_id,
                    "profile_name": str(profile.get("name") or "Без профиля"),
                    "node_id": str(node.get("id") or ""),
                    "name": str(node.get("name") or normalized.get("display_name") or "Без имени"),
                    "protocol": str(node.get("protocol") or normalized.get("protocol") or "").upper(),
                    "endpoint": endpoint_label(normalized),
                    "enabled": bool(profile.get("enabled", True) and node.get("enabled", True)),
                    "active": profile_id == active_profile_id and node.get("id") == active_node_id,
                    "parse_error": str(node.get("parse_error") or ""),
                }
            )
    return nodes


def endpoint_label(normalized: dict[str, Any]) -> str:
    address = str(normalized.get("address") or "").strip()
    port = normalized.get("port")
    if address and port:
        return f"{address}:{port}"
    return address or "—"


class WindowsCoreService:
    def __init__(self, context: WindowsCoreContext) -> None:
        self.context = context

    def ensure_store(self) -> dict[str, Any]:
        return ensure_store_initialized(self.context.app_paths, self.context.project_root)

    def persist_store(self, store: dict[str, Any]) -> None:
        save_store(self.context.app_paths, store)
        sync_generated_runtime(store, self.context.app_paths, self.context.project_root)

    def runtime_is_running(self, state: dict[str, Any]) -> bool:
        return str(state.get("state") or "").lower() == "running"

    def runtime_controller(self) -> WindowsRuntimeController:
        return WindowsRuntimeController(
            project_root=self.context.project_root,
            config_path=self.context.app_paths.generated_xray_config_file,
            active_config_path=self.context.app_paths.active_runtime_xray_config_file,
            runtime_dir=self.context.runtime_dir,
            state_file=self.context.runtime_state_file,
            log_dir=self.context.log_dir,
            diagnostic_dir=self.context.diagnostic_dir,
        )

    def build_status(self) -> dict[str, Any]:
        store = self.ensure_store()
        payload = store_payload(store, self.context.app_paths)
        active_profile = payload.get("active_profile")
        active_node = payload.get("active_node")
        active_routing_profile = payload.get("active_routing_profile")
        routing_state = payload.get("store", {}).get("routing") if isinstance(payload.get("store"), dict) else {}
        if not isinstance(routing_state, dict):
            routing_state = {}
        direct_report = build_direct_routes_report(
            template_config=read_json_config(self.context.project_root / "xray-tun-subvost.json"),
            active_profile=active_routing_profile if isinstance(active_routing_profile, dict) else None,
            runtime_config=read_json_config(self.context.app_paths.generated_xray_config_file),
        )
        active_node_name = "—"
        if isinstance(active_node, dict):
            active_node_name = str(active_node.get("name") or "Без имени")

        runtime_state = self.runtime_controller().inspect()
        running = self.runtime_is_running(runtime_state)
        generated_config_exists = self.context.app_paths.generated_xray_config_file.exists()
        start_ready = bool(active_profile and active_node and generated_config_exists)
        label = "Подключение активно" if running else "Подключение отключено"
        description = (
            "Windows runtime отмечен как активный в state-файле."
            if running
            else "Windows runtime не запущен этим служебным модулем."
        )
        if not start_ready and not running:
            description = "Выбери валидный узел перед подключением."

        return {
            "summary": {
                "state": "running" if running else "stopped",
                "label": label,
                "description": description,
                "stack_line": "Xray core",
                "stack_subline": "Служебный модуль Windows без браузерного backend",
                "tun_line": str(runtime_state.get("adapter") or WINDOWS_TUN_ADAPTER),
                "dns_line": str(runtime_state.get("dns") or "DNS будет проверен runtime-адаптером"),
                "logs_line": str(self.context.log_dir),
                "badges": [
                    label,
                    "готов к старту" if start_ready else "нужен узел",
                    "нативный Windows UI",
                ],
            },
            "runtime": {
                "mode": "windows-helper",
                "mode_label": "Нативный служебный модуль Windows без HTTP backend.",
                "impl": "xray-wintun",
                "start_ready": start_ready,
                "start_blocked": not start_ready and not running,
                "next_start_reason": "Можно запускать выбранный узел." if start_ready else "Нет активного валидного узла.",
                "active_xray_config": str(self.context.app_paths.generated_xray_config_file),
                "state_file": str(self.context.runtime_state_file),
                "connected_since": runtime_state.get("started_at"),
            },
            "processes": {
                "xray_pid": runtime_state.get("xray_pid"),
                "xray_alive": running,
                "tun_present": running,
                "tun_interface": str(runtime_state.get("adapter") or WINDOWS_TUN_ADAPTER),
                "ownership": "current" if running else "unknown",
            },
            "connection": {
                "active_name": active_node_name,
                "remote_endpoint": active_endpoint(active_node),
                "protocol_label": active_protocol(active_node),
                "tun_interface": str(runtime_state.get("adapter") or WINDOWS_TUN_ADAPTER),
                "dns_servers": str(runtime_state.get("dns") or "—"),
            },
            "store_summary": payload["summary"],
            "active_profile": active_profile,
            "active_node": active_node,
            "active_routing_profile": active_routing_profile,
            "routing": {
                **routing_state,
                "active_profile": active_routing_profile,
                "direct_report": direct_report,
            },
            "direct_report": direct_report,
            "artifacts": {
                "store_file": str(self.context.app_paths.store_file),
                "generated_xray_config": str(self.context.app_paths.generated_xray_config_file),
                "log_dir": str(self.context.log_dir),
                "latest_diagnostic": self.latest_diagnostic_path(),
            },
            "project_root": str(self.context.project_root),
            "gui_version": GUI_VERSION,
            "timestamp": iso_now(),
        }

    def latest_diagnostic_path(self) -> str | None:
        if not self.context.diagnostic_dir.exists():
            return None
        candidates = sorted(self.context.diagnostic_dir.glob("subvost-win81-diagnostic-*.json"), reverse=True)
        return str(candidates[0]) if candidates else None

    def status_envelope(self, command: str = "status") -> dict[str, Any]:
        store = store_payload(self.ensure_store(), self.context.app_paths)
        status = self.build_status()
        return envelope(
            ok=True,
            command=command,
            message=str(status.get("summary", {}).get("label") or "Статус получен."),
            data={"nodes": flatten_nodes(store["store"])},
            status=status,
            store=store,
        )

    def runtime_start(self) -> dict[str, Any]:
        status = self.build_status()
        if not status["runtime"]["start_ready"]:
            raise CommandError(str(status["runtime"]["next_start_reason"]), data={"status": status})
        state = self.runtime_controller().start()
        status = self.build_status()
        return envelope(
            ok=True,
            command="runtime start",
            message="Подключение запущено через Windows runtime-адаптер.",
            data={"runtime_state": state},
            status=status,
            store=store_payload(self.ensure_store(), self.context.app_paths),
        )

    def runtime_stop(self) -> dict[str, Any]:
        status = self.build_status()
        if status["summary"]["state"] == "stopped":
            return envelope(
                ok=True,
                command="runtime stop",
                message="Остановка не нужна: подключение уже отключено.",
                status=status,
                store=store_payload(self.ensure_store(), self.context.app_paths),
            )
        state = self.runtime_controller().stop()
        status = self.build_status()
        return envelope(
            ok=True,
            command="runtime stop",
            message="Подключение остановлено, маршруты rollback выполнены.",
            data={"runtime_state": state},
            status=status,
            store=store_payload(self.ensure_store(), self.context.app_paths),
        )

    def capture_diagnostics(self) -> dict[str, Any]:
        diagnostic = self.runtime_controller().capture_diagnostics()
        return envelope(
            ok=True,
            command="diagnostics capture",
            message=f"Диагностика сохранена: {diagnostic['path']}",
            data={"diagnostic_path": diagnostic["path"], "diagnostic": diagnostic["diagnostic"]},
            status=self.build_status(),
            store=store_payload(self.ensure_store(), self.context.app_paths),
        )

    def subscriptions_list(self) -> dict[str, Any]:
        store = self.ensure_store()
        payload = store_payload(store, self.context.app_paths)
        return envelope(
            ok=True,
            command="subscriptions list",
            message="Список подписок получен.",
            data={"subscriptions": store.get("subscriptions", [])},
            status=self.build_status(),
            store=payload,
        )

    def subscriptions_add(self, name: str, url: str, *, refresh: bool) -> dict[str, Any]:
        store = self.ensure_store()
        subscription = store_add_subscription(store, name, url)
        refresh_result: dict[str, Any] | None = None
        refresh_error = ""
        if refresh:
            try:
                refresh_result = store_refresh_subscription(store, subscription["id"], paths=self.context.app_paths)
            except Exception as exc:
                refresh_error = str(exc)
                subscription["last_status"] = "error"
                subscription["last_error"] = refresh_error
        self.persist_store(store)
        status = self.build_status()
        ok = not refresh_error
        message = (
            f"Подписка добавлена: {subscription['name']}."
            if ok
            else f"Подписка сохранена, но обновление не выполнено: {refresh_error}"
        )
        return envelope(
            ok=ok,
            command="subscriptions add",
            message=message,
            data={"subscription": subscription, "refresh": refresh_result, "refresh_error": refresh_error},
            status=status,
            store=store_payload(store, self.context.app_paths),
            error={"message": refresh_error, "type": "refresh"} if refresh_error else None,
        )

    def subscriptions_refresh(self, subscription_id: str) -> dict[str, Any]:
        store = self.ensure_store()
        result = store_refresh_subscription(store, subscription_id, paths=self.context.app_paths)
        self.persist_store(store)
        return envelope(
            ok=True,
            command="subscriptions refresh",
            message=f"Подписка обновлена: сохранено {result['unique_nodes']} уникальных узлов.",
            data={"refresh": result},
            status=self.build_status(),
            store=store_payload(store, self.context.app_paths),
        )

    def subscriptions_refresh_all(self) -> dict[str, Any]:
        store = self.ensure_store()
        result = store_refresh_all_subscriptions(store, paths=self.context.app_paths)
        self.persist_store(store)
        ok = int(result.get("error") or 0) == 0
        return envelope(
            ok=ok,
            command="subscriptions refresh-all",
            message="Все включённые подписки обновлены." if ok else "Часть подписок не обновилась.",
            data={"refresh_all": result},
            status=self.build_status(),
            store=store_payload(store, self.context.app_paths),
            error=None if ok else {"message": "Часть подписок не обновилась.", "type": "refresh_all"},
        )

    def nodes_list(self) -> dict[str, Any]:
        store = self.ensure_store()
        payload = store_payload(store, self.context.app_paths)
        nodes = flatten_nodes(store)
        return envelope(
            ok=True,
            command="nodes list",
            message=f"Найдено узлов: {len(nodes)}.",
            data={"nodes": nodes},
            status=self.build_status(),
            store=payload,
        )

    def nodes_activate(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self.ensure_store()
        node = store_activate_selection(store, profile_id, node_id, source="windows-ui")
        self.persist_store(store)
        return envelope(
            ok=True,
            command="nodes activate",
            message=f"Активным сделан узел: {node.get('name') or 'без имени'}.",
            data={"node": node},
            status=self.build_status(),
            store=store_payload(store, self.context.app_paths),
        )

    def config_active(self) -> dict[str, Any]:
        status = self.build_status()
        config_path = self.context.app_paths.generated_xray_config_file
        config = read_json_file(config_path)
        return envelope(
            ok=bool(config),
            command="config active",
            message="Активный конфиг получен." if config else "Активный конфиг ещё не создан.",
            data={"path": str(config_path), "config": config},
            status=status,
            store=store_payload(self.ensure_store(), self.context.app_paths),
            error=None if config else {"message": "Активный конфиг ещё не создан.", "type": "missing_config"},
        )


def active_endpoint(active_node: object) -> str:
    if not isinstance(active_node, dict):
        return "—"
    return endpoint_label(active_node.get("normalized") or {})


def active_protocol(active_node: object) -> str:
    if not isinstance(active_node, dict):
        return "—"
    normalized = active_node.get("normalized") or {}
    return str(active_node.get("protocol") or normalized.get("protocol") or "—").upper()


def option_value(argv: list[str], name: str, default: str = "") -> str:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise CommandError(f"Не передано значение для {name}.")
    return argv[index + 1]


def dispatch(service: WindowsCoreService, argv: list[str]) -> dict[str, Any]:
    args = [item for item in argv if item != "--json"]
    if not args or args == ["status"]:
        return service.status_envelope("status")

    if args[:2] == ["runtime", "start"]:
        return service.runtime_start()
    if args[:2] == ["runtime", "stop"]:
        return service.runtime_stop()
    if args[:2] == ["diagnostics", "capture"]:
        return service.capture_diagnostics()
    if args[:2] == ["subscriptions", "list"]:
        return service.subscriptions_list()
    if args[:2] == ["subscriptions", "add"]:
        name = option_value(args, "--name")
        url = option_value(args, "--url")
        return service.subscriptions_add(name, url, refresh="--no-refresh" not in args)
    if args[:2] == ["subscriptions", "refresh"]:
        return service.subscriptions_refresh(option_value(args, "--subscription-id"))
    if args[:2] == ["subscriptions", "refresh-all"]:
        return service.subscriptions_refresh_all()
    if args[:2] == ["nodes", "list"]:
        return service.nodes_list()
    if args[:2] == ["nodes", "activate"]:
        return service.nodes_activate(option_value(args, "--profile-id"), option_value(args, "--node-id"))
    if args[:2] == ["config", "active"]:
        return service.config_active()

    raise CommandError(f"Неизвестная команда служебного модуля: {command_name(args)}")


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    command = command_name(raw_args)
    try:
        context = build_context()
        service = WindowsCoreService(context)
        payload = dispatch(service, raw_args)
    except CommandError as exc:
        payload = envelope(
            ok=False,
            command=command,
            message=str(exc),
            data=exc.data,
            status=exc.data.get("status", {}) if isinstance(exc.data, dict) else {},
            error={"message": str(exc), "type": exc.__class__.__name__},
        )
    except Exception as exc:
        payload = envelope(
            ok=False,
            command=command,
            message=str(exc),
            error={"message": str(exc), "type": exc.__class__.__name__},
        )

    write_json_stdout(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
