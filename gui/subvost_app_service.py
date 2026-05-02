from __future__ import annotations

import copy
import json
import os
import pwd
import re
import socket
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gui_contract import GUI_VERSION
from subvost_paths import AppPaths, build_app_paths
from subvost_routing import build_direct_routes_report
from subvost_runtime import node_can_render_runtime, read_json_config
from subvost_store import (
    activate_routing_profile as store_activate_routing_profile,
    activate_selection as store_activate_selection,
    add_subscription as store_add_subscription,
    clear_active_routing_profile as store_clear_active_routing_profile,
    delete_node as store_delete_node,
    delete_profile as store_delete_profile,
    delete_subscription as store_delete_subscription,
    ensure_store_initialized,
    get_active_node,
    get_active_routing_profile,
    import_routing_profile as store_import_routing_profile,
    prepare_routing_runtime as store_prepare_routing_runtime,
    read_gui_settings,
    refresh_all_subscriptions as store_refresh_all_subscriptions,
    refresh_subscription as store_refresh_subscription,
    save_gui_settings,
    save_store,
    set_routing_enabled as store_set_routing_enabled,
    store_payload,
    sync_generated_runtime,
    update_node as store_update_node,
    update_profile as store_update_profile,
    update_routing_profile_enabled as store_update_routing_profile_enabled,
    update_subscription as store_update_subscription,
)

INSTALL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{7,127}$")
DEFAULT_ARTIFACT_RETENTION_DAYS = 7


def discover_project_root(gui_dir: Path) -> Path:
    explicit_root = os.environ.get("SUBVOST_PROJECT_ROOT")
    if explicit_root:
        candidate = Path(explicit_root)
        if not candidate.is_absolute():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT должен быть абсолютным путём: {explicit_root}")
        if not candidate.is_dir():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT не найден: {explicit_root}")
        return candidate

    candidate = gui_dir.parent
    if candidate.is_dir():
        return candidate

    raise SystemExit(f"Не удалось определить корень bundle рядом с {gui_dir}")


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


def validate_install_id(value: str | None) -> bool:
    return bool(value and INSTALL_ID_PATTERN.fullmatch(value))


def ensure_bundle_install_id(project_root: Path) -> str:
    install_id_file = project_root / ".subvost" / "install-id"
    if install_id_file.exists():
        lines = install_id_file.read_text(encoding="utf-8").splitlines()
        install_id = lines[0].strip() if lines else ""
        if not validate_install_id(install_id):
            raise SystemExit(f"Некорректный install-id установки: {install_id_file}")
        return install_id

    install_id_file.parent.mkdir(parents=True, exist_ok=True)
    install_id = str(uuid.uuid4())
    install_id_file.write_text(f"{install_id}\n", encoding="utf-8")
    try:
        install_id_file.chmod(0o600)
    except OSError:
        pass
    try:
        real_user, _ = discover_real_user()
        pw_entry = pwd.getpwnam(real_user)
        os.chown(install_id_file.parent, pw_entry.pw_uid, pw_entry.pw_gid)
        os.chown(install_id_file, pw_entry.pw_uid, pw_entry.pw_gid)
    except (OSError, KeyError):
        pass
    return install_id


def runtime_source_label(source: str | None) -> str:
    if source == "store":
        return "Выбранный узел"
    if source == "custom":
        return "Пользовательский конфиг"
    if source == "blocked":
        return "Старт заблокирован"
    return "Не определён"


def default_last_action() -> dict[str, Any]:
    return {
        "name": None,
        "ok": None,
        "message": "Интерфейс готов. Действия выполняются через существующие shell-скрипты.",
        "timestamp": None,
        "details": "",
    }


def default_last_traffic_sample() -> dict[str, Any]:
    return {
        "interface": None,
        "timestamp": None,
        "rx_bytes": None,
        "tx_bytes": None,
    }


@dataclass
class CommandResult:
    name: str
    ok: bool
    returncode: int
    output: str


@dataclass(frozen=True)
class ServiceContext:
    project_root: Path
    real_user: str
    real_home: Path
    real_uid: int
    real_gid: int
    app_paths: AppPaths
    state_file: Path
    resolv_backup: Path
    log_dir: Path
    run_script: Path
    stop_script: Path
    diag_script: Path
    xray_update_script: Path
    xray_template_path: Path
    install_id: str = "test-install-id"


@dataclass
class ServiceState:
    last_action: dict[str, Any] = field(default_factory=default_last_action)
    action_log: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=200))
    ping_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    ping_cache_lock: threading.Lock = field(default_factory=threading.Lock)
    traffic_sample_lock: threading.Lock = field(default_factory=threading.Lock)
    last_traffic_sample: dict[str, Any] = field(default_factory=default_last_traffic_sample)


def build_default_service(gui_dir: Path, *, state: ServiceState | None = None) -> "SubvostAppService":
    project_root = discover_project_root(gui_dir)
    real_user, real_home = discover_real_user()
    pw_entry = pwd.getpwnam(real_user)
    app_paths = build_app_paths(real_home)
    context = ServiceContext(
        project_root=project_root,
        real_user=real_user,
        real_home=real_home,
        real_uid=pw_entry.pw_uid,
        real_gid=pw_entry.pw_gid,
        app_paths=app_paths,
        state_file=real_home / ".xray-tun-subvost.state",
        resolv_backup=real_home / ".xray-tun-subvost.resolv.conf.backup",
        log_dir=project_root / "logs",
        run_script=project_root / "run-xray-tun-subvost.sh",
        stop_script=project_root / "stop-xray-tun-subvost.sh",
        diag_script=project_root / "capture-xray-tun-state.sh",
        xray_update_script=project_root / "update-xray-core-subvost.sh",
        xray_template_path=project_root / "xray-tun-subvost.json",
        install_id=ensure_bundle_install_id(project_root),
    )
    return SubvostAppService(context=context, state=state)


class SubvostAppService:
    def __init__(self, *, context: ServiceContext, state: ServiceState | None = None) -> None:
        self.context = context
        self.state = state or ServiceState()

    def ping_cache_key(self, profile_id: str, node_id: str) -> str:
        return f"{profile_id}:{node_id}"

    def ping_cache_snapshot(self) -> dict[str, Any]:
        with self.state.ping_cache_lock:
            return dict(self.state.ping_cache)

    def find_profile_and_node(
        self,
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

    def load_settings(self) -> dict[str, Any]:
        return read_gui_settings(self.context.app_paths, uid=self.context.real_uid, gid=self.context.real_gid)

    def save_settings(
        self,
        file_logs_enabled: bool | None = None,
        *,
        close_to_tray: bool | None = None,
        start_minimized_to_tray: bool | None = None,
        theme: str | None = None,
        artifact_retention_days: int | None = None,
    ) -> None:
        save_gui_settings(
            self.context.app_paths,
            file_logs_enabled,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
            close_to_tray=close_to_tray,
            start_minimized_to_tray=start_minimized_to_tray,
            theme=theme,
            artifact_retention_days=artifact_retention_days,
        )

    def load_state_file(self) -> dict[str, str]:
        if not self.context.state_file.exists():
            return {}

        result: dict[str, str] = {}
        for line in self.context.state_file.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
        return result

    def state_bundle_project_root(self, state: dict[str, str]) -> str | None:
        return normalize_identity_path(state.get("BUNDLE_PROJECT_ROOT_HINT") or state.get("BUNDLE_PROJECT_ROOT"))

    def state_bundle_install_id(self, state: dict[str, str]) -> str | None:
        install_id = state.get("BUNDLE_INSTALL_ID")
        return install_id if validate_install_id(install_id) else None

    def classify_runtime_ownership(self, state: dict[str, str]) -> str:
        bundle_install_id = self.state_bundle_install_id(state)
        if bundle_install_id:
            return "current" if bundle_install_id == self.context.install_id else "foreign"

        bundle_root = self.state_bundle_project_root(state)
        if not bundle_root:
            return "unknown"

        current_root = normalize_identity_path(str(self.context.project_root)) or str(self.context.project_root)
        return "current" if bundle_root == current_root else "foreign"

    def runtime_ownership_label(self, ownership: str) -> str:
        if ownership == "current":
            return "Текущий экземпляр"
        if ownership == "foreign":
            return "Другой экземпляр"
        return "Источник не подтверждён"

    def is_pid_alive(self, value: str | None) -> bool:
        if not value or not value.isdigit():
            return False
        return Path(f"/proc/{value}").exists()

    def inspect_runtime_state(self, state: dict[str, str] | None = None) -> dict[str, Any]:
        runtime_state = self.load_state_file() if state is None else state
        tun_interface = str(runtime_state.get("TUN_INTERFACE") or "tun0").strip() or "tun0"
        xray_pid = runtime_state.get("XRAY_PID")
        xray_alive = self.is_pid_alive(xray_pid)
        tun_present = Path("/sys/class/net").joinpath(tun_interface).exists()
        stack_is_live = xray_alive or tun_present
        has_state = bool(runtime_state)
        ownership = self.classify_runtime_ownership(runtime_state) if has_state else "unknown"
        owned_stack_is_live = ownership == "current" and stack_is_live

        return {
            "state": runtime_state,
            "has_state": has_state,
            "ownership": ownership,
            "ownership_label": self.runtime_ownership_label(ownership),
            "state_bundle_install_id": self.state_bundle_install_id(runtime_state),
            "state_bundle_project_root": self.state_bundle_project_root(runtime_state),
            "tun_interface": tun_interface,
            "xray_pid": xray_pid,
            "xray_alive": xray_alive,
            "tun_present": tun_present,
            "stack_is_live": stack_is_live,
            "owned_stack_is_live": owned_stack_is_live,
        }

    def artifact_file_summary(self, path: Path) -> dict[str, Any]:
        exists = path.exists()
        result: dict[str, Any] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": 0,
            "mtime": None,
            "is_file": False,
            "is_symlink": False,
        }
        if not exists:
            return result

        try:
            stat = path.stat()
            result.update(
                {
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    "is_file": path.is_file(),
                    "is_symlink": path.is_symlink(),
                }
            )
        except OSError as exc:
            result["error"] = str(exc)
        return result

    def managed_log_artifact_candidates(self) -> list[Path]:
        if not self.context.log_dir.exists():
            return []
        candidates: list[Path] = []
        for pattern in ("xray-tun-state-*.log", "native-shell-log-export-*.log"):
            candidates.extend(self.context.log_dir.glob(pattern))
        return sorted(set(candidates), key=lambda item: str(item))

    def retained_log_artifact_summary(self, retention_days: int) -> dict[str, Any]:
        cutoff = datetime.now().astimezone() - timedelta(days=retention_days)
        candidates = self.managed_log_artifact_candidates()
        expired: list[dict[str, Any]] = []
        fresh: list[dict[str, Any]] = []

        for candidate in candidates:
            item = self.artifact_file_summary(candidate)
            mtime = item.get("mtime")
            is_expired = False
            if isinstance(mtime, str):
                try:
                    is_expired = datetime.fromisoformat(mtime) < cutoff
                except ValueError:
                    is_expired = False
            if is_expired:
                expired.append(item)
            else:
                fresh.append(item)

        return {
            "retention_days": retention_days,
            "total_count": len(candidates),
            "expired_count": len(expired),
            "fresh_count": len(fresh),
            "expired": expired,
            "fresh_latest": sorted(fresh, key=lambda item: str(item.get("mtime") or ""), reverse=True)[:5],
        }

    def cleanup_retained_log_artifacts(self, retention_days: int) -> dict[str, Any]:
        summary = self.retained_log_artifact_summary(retention_days)
        deleted: list[str] = []
        skipped: list[dict[str, str]] = []

        for item in summary["expired"]:
            path = Path(str(item.get("path") or ""))
            if not item.get("is_file") or item.get("is_symlink"):
                skipped.append({"path": str(path), "reason": "не обычный файл"})
                continue
            try:
                path.unlink()
                deleted.append(str(path))
            except OSError as exc:
                skipped.append({"path": str(path), "reason": str(exc)})

        return {
            "deleted": deleted,
            "skipped": skipped,
            "deleted_count": len(deleted),
            "skipped_count": len(skipped),
            "retention_days": retention_days,
        }

    def settings_artifact_retention_days(self) -> int:
        settings = self.load_settings()
        try:
            retention_days = int(settings.get("artifact_retention_days") or DEFAULT_ARTIFACT_RETENTION_DAYS)
        except (TypeError, ValueError):
            retention_days = DEFAULT_ARTIFACT_RETENTION_DAYS
        return min(365, max(1, retention_days))

    def cleanup_retained_log_artifacts_from_settings(self) -> dict[str, Any]:
        return self.cleanup_retained_log_artifacts(self.settings_artifact_retention_days())

    def build_runtime_artifacts_audit(
        self,
        *,
        runtime_info: dict[str, Any],
        retention_days: int,
        retention_cleanup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        has_state = bool(runtime_info["has_state"])
        stack_is_live = bool(runtime_info["stack_is_live"])
        ownership = str(runtime_info["ownership"])
        state_status = "missing"
        state_label = "State-файл отсутствует"
        state_cleanup_available = False
        manual_required = False
        manual_reason = ""

        if has_state and stack_is_live and ownership == "current":
            state_status = "active_current"
            state_label = "State-файл текущего подключения"
        elif has_state and stack_is_live:
            state_status = "manual_required"
            state_label = "State-файл живого подключения другого или неподтверждённого экземпляра"
            manual_required = True
            manual_reason = "Живой runtime не очищается автоматически."
        elif has_state:
            state_status = "stale"
            state_label = "Устаревший state-файл без живого runtime"
            state_cleanup_available = True

        backup_summary = self.artifact_file_summary(self.context.resolv_backup)
        backup_orphan = bool(backup_summary["exists"] and not has_state and not stack_is_live)
        retention_summary = self.retained_log_artifact_summary(retention_days)
        cleanup_available = state_cleanup_available or backup_orphan or retention_summary["expired_count"] > 0

        return {
            "runtime_state_status": {
                "status": state_status,
                "label": state_label,
                "cleanup_available": state_cleanup_available,
                "manual_attention_required": manual_required,
                "manual_reason": manual_reason,
                "file": self.artifact_file_summary(self.context.state_file),
                "ownership": ownership,
                "stack_is_live": stack_is_live,
                "xray_pid": runtime_info.get("xray_pid"),
                "tun_interface": runtime_info.get("tun_interface"),
                "state_bundle_install_id": runtime_info.get("state_bundle_install_id"),
                "state_bundle_project_root": runtime_info.get("state_bundle_project_root"),
            },
            "resolv_backup_status": {
                **backup_summary,
                "orphan": backup_orphan,
                "cleanup_available": backup_orphan,
            },
            "diagnostic_dumps": retention_summary,
            "retention_days": retention_days,
            "cleanup_available": cleanup_available,
            "manual_attention_required": manual_required,
            "manual_reason": manual_reason,
            "cleanup_summary": retention_cleanup or {"deleted": [], "skipped": [], "deleted_count": 0, "skipped_count": 0},
        }

    def cleanup_runtime_artifacts(self) -> dict[str, Any]:
        retention_days = self.settings_artifact_retention_days()
        runtime_info = self.inspect_runtime_state()
        cleanup_results: list[str] = []
        errors: list[str] = []
        state_preserved = False
        state_cleanup_attempted = False
        manual_blocked = False
        backup_deleted = False

        if runtime_info["has_state"] and runtime_info["stack_is_live"] and runtime_info["ownership"] == "current":
            state_preserved = True
            cleanup_results.append("State текущего подключения сохранён: runtime активен.")
        elif runtime_info["has_state"] and runtime_info["stack_is_live"]:
            manual_blocked = True
            errors.append("Очистка требует ручного контроля: живой runtime не очищается автоматически.")
        elif runtime_info["has_state"]:
            state_cleanup_attempted = True
            result = self.run_shell_action("Очистка служебных файлов", self.context.stop_script)
            cleanup_results.append(result.output)
            if not result.ok:
                errors.append(f"Очистка state завершилась ошибкой, код {result.returncode}.")

        refreshed_runtime = self.inspect_runtime_state()
        if self.context.resolv_backup.exists() and not refreshed_runtime["has_state"] and not refreshed_runtime["stack_is_live"]:
            try:
                self.context.resolv_backup.unlink()
                backup_deleted = True
                cleanup_results.append(f"Удалён orphan DNS backup: {self.context.resolv_backup}")
            except OSError as exc:
                errors.append(f"Не удалось удалить DNS backup: {exc}")

        retention_cleanup = self.cleanup_retained_log_artifacts(retention_days)
        if retention_cleanup["deleted_count"]:
            cleanup_results.append(f"Удалено старых диагностических файлов: {retention_cleanup['deleted_count']}")
        if retention_cleanup["skipped_count"]:
            errors.append(f"Пропущено файлов при retention cleanup: {retention_cleanup['skipped_count']}")

        ok = not errors
        changed = bool(state_cleanup_attempted or backup_deleted or retention_cleanup["deleted_count"])
        if manual_blocked and not changed:
            message = "Очистка требует ручного контроля: живой runtime не очищается автоматически."
        elif errors:
            message = f"Очистка служебных файлов выполнена частично: {errors[0]}"
        elif changed:
            message = "Служебные файлы очищены."
        elif state_preserved:
            message = "Очистка не требуется: state относится к текущему подключению, DNS backup сохранён."
        else:
            message = "Очистка не требуется: безопасно очищаемые служебные файлы не найдены."
        details = "\n".join([item for item in cleanup_results if item] + errors) or "cleanup=nothing-to-delete"
        self.remember_action("Очистка служебных файлов", ok, message, details)
        return self.collect_status(retention_cleanup=retention_cleanup)

    def runtime_control_blocked(self, runtime_info: dict[str, Any]) -> bool:
        ownership = runtime_info["ownership"]
        if ownership == "foreign":
            return bool(runtime_info["stack_is_live"])
        if ownership == "unknown":
            return bool(runtime_info["stack_is_live"])
        return False

    def runtime_control_guard_message(self, runtime_info: dict[str, Any], *, action: str) -> str:
        state_root = runtime_info.get("state_bundle_project_root")
        state_install_id = runtime_info.get("state_bundle_install_id")
        tun_interface = runtime_info.get("tun_interface") or "tun0"
        current_root = str(self.context.project_root)

        if runtime_info["ownership"] == "foreign":
            identity_line = (
                f"Идентификатор установки: {state_install_id}."
                if state_install_id
                else f"Он запущен из: {state_root}."
            )
            base = (
                f"Обнаружено активное подключение другого экземпляра Subvost. "
                f"{identity_line} Текущий проект: {current_root}."
            )
        elif runtime_info["has_state"]:
            base = (
                f"Обнаружен state-файл без подтверждённой identity: {self.context.state_file}. "
                "Для безопасности источник этого подключения пока не считается подтверждённым."
            )
        else:
            base = (
                "Обнаружено активное подключение без подтверждённой identity. "
                f"Интерфейс: {tun_interface}."
            )

        if action == "close":
            return base + " Окно закроется без остановки этого подключения."
        if action == "start":
            return base + " Сначала остановите или проверьте исходный экземпляр, затем повторите запуск."
        return base + " Текущий экземпляр не будет управлять этим подключением."

    def runtime_stop_required(self, state: dict[str, str] | None = None) -> bool:
        runtime_info = self.inspect_runtime_state(state)
        return bool(runtime_info["owned_stack_is_live"])

    def read_interface_byte_counter(self, interface_name: str, direction: str) -> int | None:
        if not interface_name:
            return None
        counter_path = Path("/sys/class/net") / interface_name / "statistics" / f"{direction}_bytes"
        if not counter_path.exists():
            return None
        try:
            return int(counter_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def collect_traffic_metrics(self, interface_name: str) -> dict[str, Any]:
        rx_bytes = self.read_interface_byte_counter(interface_name, "rx")
        tx_bytes = self.read_interface_byte_counter(interface_name, "tx")
        now = time.monotonic()
        rx_rate = 0.0
        tx_rate = 0.0

        with self.state.traffic_sample_lock:
            previous = self.state.last_traffic_sample.copy()
            self.state.last_traffic_sample.update(
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

    def tail_text_file(self, path: Path, *, max_bytes: int = 24000) -> str:
        if not path.exists():
            return ""
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            chunk = handle.read()
        return chunk.decode("utf-8", errors="ignore")

    def collect_log_payload(self) -> dict[str, Any]:
        action_entries = list(self.state.action_log)
        file_entries: list[dict[str, Any]] = []
        log_file = self.context.log_dir / "xray-subvost.log"
        tail = self.tail_text_file(log_file)
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

    def read_resolv_conf_nameservers(self) -> list[str]:
        resolv_path = Path("/etc/resolv.conf")
        if not resolv_path.exists():
            return []

        servers: list[str] = []
        for line in resolv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("nameserver "):
                servers.append(line.split()[1])
        return servers

    def read_interface_addresses(self, interface_name: str) -> str:
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
        self,
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
                "label": "Активен другой экземпляр",
                "description": f"Сейчас подключением управляет другой экземпляр. Интерфейс: {tun_label}.",
                "stack_line": "Xray core",
                "stack_subline": "Чужое подключение, управление заблокировано",
            }

        if ownership == "unknown" and (xray_alive or tun_present):
            return {
                "state": "degraded",
                "label": "Источник не подтверждён",
                "description": f"Обнаружено активное подключение без подтверждённого владельца. Интерфейс: {tun_label}.",
                "stack_line": "Xray core",
                "stack_subline": "Источник подключения не подтверждён",
            }

        if xray_alive and tun_present:
            return {
                "state": "running",
                "label": "Подключение активно",
                "description": f"Xray и {tun_label} активны.",
                "stack_line": "Xray core",
                "stack_subline": "Единый TUN-контур проекта",
            }
        if xray_alive or tun_present:
            return {
                "state": "degraded",
                "label": "Состояние частичное",
                "description": f"Часть подключения активна, стоит снять диагностику. Интерфейс: {tun_label}.",
                "stack_line": "Xray core",
                "stack_subline": "Единый TUN-контур проекта",
            }
        return {
            "state": "stopped",
            "label": "Подключение отключено",
            "description": f"Подключение не запущено, {tun_label} не поднят.",
            "stack_line": "Xray core",
            "stack_subline": "Единый TUN-контур проекта",
        }

    def find_latest_diagnostic(self) -> Path | None:
        if not self.context.log_dir.exists():
            return None
        candidates = sorted(
            self.context.log_dir.glob("xray-tun-state-*.log"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def normalize_output(self, text: str, limit: int = 12000) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "Команда не вернула текстовый вывод."
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[-limit:]

    def append_action_log_entry(
        self,
        *,
        name: str,
        level: str,
        message: str,
        details: str = "",
        source: str = "action",
    ) -> None:
        self.state.action_log.append(
            {
                "timestamp": iso_now(),
                "name": name,
                "level": level,
                "message": message,
                "details": self.normalize_output(details, limit=4000) if details else "",
                "source": source,
            }
        )

    def remember_action(self, name: str, ok: bool | None, message: str, details: str) -> None:
        normalized_details = self.normalize_output(details)
        self.state.last_action.update(
            {
                "name": name,
                "ok": ok,
                "message": message,
                "timestamp": iso_now(),
                "details": normalized_details,
            }
        )
        self.append_action_log_entry(
            name=name,
            level="error" if ok is False else "info",
            message=message,
            details=normalized_details,
        )

    def build_shell_action_env(self, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        action_env = {
            "SUDO_USER": self.context.real_user,
            "USER": self.context.real_user,
            "LOGNAME": self.context.real_user,
            "HOME": str(self.context.real_home),
            "SUBVOST_PROJECT_ROOT": str(self.context.project_root),
            "SUBVOST_REAL_USER": self.context.real_user,
            "SUBVOST_REAL_HOME": str(self.context.real_home),
            "SUBVOST_REAL_XDG_CONFIG_HOME": str(self.context.app_paths.config_home),
        }
        action_env.update(extra_env or {})
        return action_env

    def build_shell_action_command(self, script: Path, action_env: dict[str, str]) -> list[str]:
        if os.geteuid() == 0:
            return [str(script)]

        pkexec_env = [f"{key}={value}" for key, value in action_env.items()]
        return ["pkexec", "env", *pkexec_env, "/usr/bin/env", "bash", str(script)]

    def run_shell_action(self, name: str, script: Path, extra_env: dict[str, str] | None = None) -> CommandResult:
        env = os.environ.copy()
        action_env = self.build_shell_action_env(extra_env)
        env.update(action_env)
        command = self.build_shell_action_command(script, action_env)

        try:
            completed = subprocess.run(
                command,
                cwd=self.context.project_root,
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

    def ensure_store_ready(self) -> dict[str, Any]:
        return ensure_store_initialized(
            self.context.app_paths,
            self.context.project_root,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
        )

    def persist_store(self, store: dict[str, Any]) -> None:
        save_store(self.context.app_paths, store, uid=self.context.real_uid, gid=self.context.real_gid)
        sync_generated_runtime(
            store,
            self.context.app_paths,
            self.context.project_root,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
        )

    def resolve_active_xray_config_path(
        self,
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

        return self.context.app_paths.generated_xray_config_file

    def describe_runtime_state(
        self,
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
            and self.context.app_paths.generated_xray_config_file.exists()
        )

        if start_ready:
            next_start_source = "store"
            next_start_reason = "При следующем запуске будет использован сгенерированный конфиг выбранного узла."
        else:
            next_start_source = "blocked"
            next_start_reason = "Старт невозможен, пока не выбран и не подготовлен валидный узел."

        if routing_state.get("enabled") and not routing_state.get("runtime_ready"):
            start_ready = False
            next_start_source = "blocked"
            next_start_reason = str(routing_state.get("runtime_error") or "Маршрутизация включена, но не готова.")

        start_blocked = self.runtime_control_blocked(runtime_info)
        if start_blocked:
            start_ready = False
            next_start_source = "blocked"
            next_start_reason = self.runtime_control_guard_message(runtime_info, action="start")

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
            "state_bundle_install_id": runtime_info.get("state_bundle_install_id"),
            "state_bundle_project_root": runtime_info["state_bundle_project_root"],
            "has_state": runtime_info["has_state"],
            "stack_is_live": runtime_info["stack_is_live"],
            "start_blocked": start_blocked,
            "stop_allowed": not start_blocked,
            "control_message": self.runtime_control_guard_message(runtime_info, action="stop") if start_blocked else "",
            "generated_path": str(self.context.app_paths.generated_xray_config_file),
            "routing_enabled": bool(routing_state.get("enabled")),
            "routing_ready": bool(routing_state.get("runtime_ready")),
            "routing_error": str(routing_state.get("runtime_error") or ""),
            "routing_profile_name": active_routing_profile.get("name") if active_routing_profile else "",
        }

    def parse_connection_info(
        self,
        xray: dict[str, Any],
        active_node: dict[str, Any] | None,
        *,
        tun_interface: str,
    ) -> dict[str, str]:
        remote_endpoint = "—"
        remote_sni = "—"
        socks_port = "127.0.0.1:10808"
        tun_address = self.read_interface_addresses(tun_interface)
        protocol_label = "—"
        transport_label = "—"
        security_label = "—"
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
            network = str(stream_settings.get("network") or "").strip().lower()
            security = str(stream_settings.get("security") or "").strip().lower()
            transport_label = network.upper() if network else "TCP"
            security_label = security.upper() if security else "NONE"
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
            "transport_label": transport_label,
            "security_label": security_label,
            "active_name": active_name,
            "active_origin": active_origin,
        }

    def collect_status(self, *, retention_cleanup: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self.load_settings()
        retention_days = self.settings_artifact_retention_days()
        store = self.ensure_store_ready()
        state = self.load_state_file()
        runtime_info = self.inspect_runtime_state(state)
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
        owned_stack_is_live = runtime_info["owned_stack_is_live"]
        stack_is_live = runtime_info["stack_is_live"]
        active_xray_config_path = self.resolve_active_xray_config_path(store, state, stack_is_live=owned_stack_is_live)
        xray = read_json_config(active_xray_config_path)
        direct_report = build_direct_routes_report(
            template_config=read_json_config(self.context.xray_template_path),
            active_profile=active_routing_profile,
            runtime_config=xray,
        )
        stack_status = self.describe_stack_status(
            xray_alive=xray_alive,
            tun_present=tun_present,
            tun_interface=tun_interface,
            ownership=runtime_info["ownership"],
        )
        state_key = stack_status["state"]
        state_label = stack_status["label"]
        description = stack_status["description"]

        dns_runtime = ", ".join(self.read_resolv_conf_nameservers()) or "DNS не прочитан"
        latest_diag = self.find_latest_diagnostic()
        runtime_mode = "root-server" if os.geteuid() == 0 else "user-server"
        runtime_label = (
            "Системный режим запущен через pkexec."
            if os.geteuid() == 0
            else "Интерфейс запущен от пользователя; системные действия выполняются через pkexec."
        )
        traffic = self.collect_traffic_metrics(tun_interface)
        logs_payload = self.collect_log_payload()
        connected_since = normalize_iso_timestamp(state.get("STARTED_AT"))
        if not stack_is_live:
            connected_since = None

        log_files = []
        for candidate in [self.context.log_dir / "xray-subvost.log"]:
            if candidate.exists():
                log_files.append(str(candidate))

        store_data = store_payload(store, self.context.app_paths)
        runtime_state = self.describe_runtime_state(
            store,
            state,
            stack_is_live=owned_stack_is_live,
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
        if active_xray_config_path == self.context.app_paths.active_runtime_xray_config_file:
            config_origin = "snapshot"
        else:
            config_origin = "generated"
        artifact_audit = self.build_runtime_artifacts_audit(
            runtime_info=runtime_info,
            retention_days=retention_days,
            retention_cleanup=retention_cleanup,
        )

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
                "state_bundle_install_id": runtime_info.get("state_bundle_install_id"),
                "state_bundle_project_root": runtime_info["state_bundle_project_root"],
                "ownership": runtime_info["ownership"],
            },
            "connection": {
                **self.parse_connection_info(
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
                "direct_report": direct_report,
            },
            "direct_report": direct_report,
            "ping": {
                "cache": self.ping_cache_snapshot(),
            },
            "logs": logs_payload,
            "artifacts": {
                **artifact_audit,
                "latest_diagnostic": str(latest_diag) if latest_diag else None,
                "state_file": str(self.context.state_file),
                "resolv_backup": str(self.context.resolv_backup),
                "log_files": ", ".join(log_files) if log_files else "Логи ещё не созданы",
                "store_file": str(self.context.app_paths.store_file),
                "generated_xray_config": str(self.context.app_paths.generated_xray_config_file),
                "active_runtime_xray_config": str(self.context.app_paths.active_runtime_xray_config_file),
                "active_xray_config": str(active_xray_config_path),
                "xray_asset_dir": str(self.context.app_paths.xray_asset_dir),
                "geoip_asset_file": str(self.context.app_paths.geoip_asset_file),
                "geosite_asset_file": str(self.context.app_paths.geosite_asset_file),
            },
            "store_summary": store_data["summary"],
            "active_profile": active_profile,
            "active_node": active_node,
            "active_routing_profile": active_routing_profile,
            "bundle_identity": {
                "install_id": self.context.install_id,
                "project_root": str(self.context.project_root),
                "config_home": str(self.context.app_paths.config_home),
            },
            "project_root": str(self.context.project_root),
            "gui_version": GUI_VERSION,
            "last_action": self.state.last_action.copy(),
            "timestamp": iso_now(),
        }

    def collect_store_snapshot(self) -> dict[str, Any]:
        store = self.ensure_store_ready()
        return {
            "ok": True,
            "store": store_payload(store, self.context.app_paths),
            "status": self.collect_status(),
        }

    def build_store_response(
        self,
        store: dict[str, Any],
        *,
        name: str,
        ok: bool,
        message: str,
        details: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.persist_store(store)
        self.remember_action(name, ok, message, details)
        payload = {
            "ok": ok,
            "message": message,
            "store": store_payload(store, self.context.app_paths),
            "status": self.collect_status(),
        }
        if extra:
            payload.update(extra)
        return payload

    def add_subscription(self, name: str, url: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        subscription = store_add_subscription(store, name, url)
        details_payload: dict[str, Any] = {
            "subscription_id": subscription["id"],
            "subscription": subscription,
            "focus_profile_id": subscription["profile_id"],
        }
        try:
            refresh_result = store_refresh_subscription(
                store,
                subscription["id"],
                paths=self.context.app_paths,
                uid=self.context.real_uid,
                gid=self.context.real_gid,
            )
            details_payload["refresh"] = refresh_result
            message = (
                f"Подписка '{subscription['name']}' добавлена. "
                f"Сохранено уникальных узлов: {refresh_result['unique_nodes']}."
            )
        except ValueError as exc:
            try:
                store_delete_subscription(store, subscription["id"], paths=self.context.app_paths)
            except ValueError:
                pass
            self.persist_store(store)
            raise ValueError(f"Подписка не добавлена: {exc}.") from exc

        return self.build_store_response(
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

    def refresh_subscription(self, subscription_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        try:
            result = store_refresh_subscription(
                store,
                subscription_id,
                paths=self.context.app_paths,
                uid=self.context.real_uid,
                gid=self.context.real_gid,
            )
        except ValueError as exc:
            self.persist_store(store)
            raise ValueError(f"Подписка не обновлена: {exc}. Сохранена предыдущая версия.") from exc
        return self.build_store_response(
            store,
            name="Обновление подписки",
            ok=True,
            message=f"Подписка обновлена: сохранено {result['unique_nodes']} уникальных узлов.",
            details=json.dumps(result, ensure_ascii=False),
            extra={"refresh": result},
        )

    def refresh_all_subscriptions(self) -> dict[str, Any]:
        store = self.ensure_store_ready()
        result = store_refresh_all_subscriptions(
            store,
            paths=self.context.app_paths,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
        )
        ok = result["error"] == 0
        message = "Все включённые подписки обновлены." if ok else "Часть подписок не обновилась."
        return self.build_store_response(
            store,
            name="Обновить все подписки",
            ok=ok,
            message=message,
            details=json.dumps(result, ensure_ascii=False),
            extra={"refresh_all": result},
        )

    def update_subscription(
        self,
        subscription_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        store = self.ensure_store_ready()
        subscription = store_update_subscription(store, subscription_id, name=name, enabled=enabled)
        return self.build_store_response(
            store,
            name="Настройки подписки",
            ok=True,
            message="Настройки подписки сохранены.",
            details=json.dumps({"subscription_id": subscription["id"]}, ensure_ascii=False),
            extra={"subscription": subscription},
        )

    def delete_subscription(self, subscription_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        store_delete_subscription(store, subscription_id, paths=self.context.app_paths)
        return self.build_store_response(
            store,
            name="Удаление подписки",
            ok=True,
            message="Подписка и связанный профиль удалены.",
            details=json.dumps({"subscription_id": subscription_id}, ensure_ascii=False),
        )

    def activate_selection(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        node = store_activate_selection(store, profile_id, node_id)
        return self.build_store_response(
            store,
            name="Активация узла",
            ok=True,
            message=f"Активным сделан узел '{node['name']}'.",
            details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
            extra={"node": node},
        )

    def update_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        store = self.ensure_store_ready()
        profile = store_update_profile(store, profile_id, name=name, enabled=enabled)
        return self.build_store_response(
            store,
            name="Настройки профиля",
            ok=True,
            message="Профиль обновлён.",
            details=json.dumps({"profile_id": profile["id"]}, ensure_ascii=False),
            extra={"profile": profile},
        )

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        store_delete_profile(store, profile_id)
        return self.build_store_response(
            store,
            name="Удаление профиля",
            ok=True,
            message="Профиль удалён.",
            details=json.dumps({"profile_id": profile_id}, ensure_ascii=False),
        )

    def update_node(
        self,
        profile_id: str,
        node_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        store = self.ensure_store_ready()
        node = store_update_node(store, profile_id, node_id, name=name, enabled=enabled)
        return self.build_store_response(
            store,
            name="Настройки узла",
            ok=True,
            message="Узел обновлён.",
            details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
            extra={"node": node},
        )

    def delete_node(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        store_delete_node(store, profile_id, node_id)
        return self.build_store_response(
            store,
            name="Удаление узла",
            ok=True,
            message="Узел удалён.",
            details=json.dumps({"profile_id": profile_id, "node_id": node_id}, ensure_ascii=False),
        )

    def ping_node(self, node: dict[str, Any], *, timeout: float = 3.0) -> dict[str, Any]:
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

    def ping_node_by_id(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        profile, node = self.find_profile_and_node(store, profile_id, node_id)
        if not profile or not node:
            raise ValueError("Узел для ping не найден.")
        if not profile.get("enabled", True):
            raise ValueError("Профиль отключён.")
        if not node.get("enabled", True):
            raise ValueError("Узел отключён.")

        try:
            result = self.ping_node(node)
        except OSError as exc:
            message = f"Проверка узла не выполнена: {exc}."
            result = {
                "host": str(node.get("normalized", {}).get("address") or "—"),
                "port": node.get("normalized", {}).get("port"),
                "latency_ms": None,
                "label": "Ошибка",
                "timestamp": iso_now(),
                "ok": False,
                "error": str(exc),
            }
            with self.state.ping_cache_lock:
                self.state.ping_cache[self.ping_cache_key(profile_id, node_id)] = result
            raise ValueError(message) from exc

        with self.state.ping_cache_lock:
            self.state.ping_cache[self.ping_cache_key(profile_id, node_id)] = result

        self.remember_action(
            "Проверка узла",
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
            "status": self.collect_status(),
        }

    def import_routing_profile(self, text: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        result = store_import_routing_profile(store, self.context.app_paths, text, uid=self.context.real_uid, gid=self.context.real_gid)
        message = (
            f"Профиль маршрутизации '{result['profile']['name']}' "
            f"{'обновлён' if not result['created'] else 'импортирован'}."
        )
        return self.build_store_response(
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

    def activate_routing_profile(self, profile_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        profile = store_activate_routing_profile(
            store,
            self.context.app_paths,
            profile_id,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
        )
        return self.build_store_response(
            store,
            name="Активация маршрутизации",
            ok=True,
            message=f"Активным сделан профиль маршрутизации '{profile['name']}'.",
            details=json.dumps({"routing_profile_id": profile_id}, ensure_ascii=False),
            extra={"routing_profile": profile},
        )

    def prepare_routing_geodata(self) -> dict[str, Any]:
        store = self.ensure_store_ready()
        geodata_before = copy.deepcopy(store.get("routing", {}).get("geodata") or {})
        profile = get_active_routing_profile(store)
        if not profile:
            enabled_profiles = [
                item
                for item in store.get("routing", {}).get("profiles", [])
                if item.get("enabled", True)
            ]
            if len(enabled_profiles) == 1:
                profile = store_activate_routing_profile(
                    store,
                    self.context.app_paths,
                    str(enabled_profiles[0]["id"]),
                    uid=self.context.real_uid,
                    gid=self.context.real_gid,
                )
            else:
                raise ValueError("Сначала выбери текущий routing-профиль.")

        geodata = store_prepare_routing_runtime(
            store,
            self.context.app_paths,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
            allow_download=True,
            force_download=True,
        )
        if not geodata.get("ready"):
            raise ValueError(geodata.get("error") or "Не удалось подготовить GeoIP/GeoSite.")

        action_message = "GeoIP и GeoSite обновлены" if geodata_before.get("ready") else "GeoIP и GeoSite подготовлены"
        return self.build_store_response(
            store,
            name="Подготовка GeoIP/GeoSite",
            ok=True,
            message=f"{action_message} для профиля '{profile['name']}'.",
            details=json.dumps(
                {
                    "routing_profile_id": profile["id"],
                    "geodata_status": geodata.get("status"),
                },
                ensure_ascii=False,
            ),
            extra={"routing_profile": profile, "geodata": geodata},
        )

    def clear_active_routing_profile(self) -> dict[str, Any]:
        store = self.ensure_store_ready()
        store_clear_active_routing_profile(store, self.context.app_paths)
        return self.build_store_response(
            store,
            name="Сброс маршрутизации",
            ok=True,
            message="Активный профиль маршрутизации снят, маршрутизация выключена.",
            details="routing_active_profile_cleared=1",
        )

    def update_routing_profile_enabled(self, profile_id: str, *, enabled: bool) -> dict[str, Any]:
        store = self.ensure_store_ready()
        profile = store_update_routing_profile_enabled(store, self.context.app_paths, profile_id, enabled=enabled)
        return self.build_store_response(
            store,
            name="Настройки маршрутизации",
            ok=True,
            message="Состояние профиля маршрутизации сохранено.",
            details=json.dumps({"routing_profile_id": profile["id"], "enabled": profile["enabled"]}, ensure_ascii=False),
            extra={"routing_profile": profile},
        )

    def set_routing_enabled(self, enabled: bool) -> dict[str, Any]:
        store = self.ensure_store_ready()
        routing = store_set_routing_enabled(
            store,
            self.context.app_paths,
            enabled,
            uid=self.context.real_uid,
            gid=self.context.real_gid,
        )
        return self.build_store_response(
            store,
            name="Переключение маршрутизации",
            ok=True,
            message="Маршрутизация включена." if routing["enabled"] else "Маршрутизация выключена.",
            details=json.dumps({"enabled": routing["enabled"]}, ensure_ascii=False),
            extra={"routing": routing},
        )

    def start_runtime(self) -> dict[str, Any]:
        runtime_info = self.inspect_runtime_state()
        if self.runtime_control_blocked(runtime_info):
            raise ValueError(self.runtime_control_guard_message(runtime_info, action="start"))
        if runtime_info["owned_stack_is_live"]:
            raise ValueError("Подключение текущего экземпляра уже активно.")

        store = self.ensure_store_ready()
        active_profile, active_node = get_active_node(store)
        routing_state = store.get("routing", {})
        if routing_state.get("enabled") and not routing_state.get("runtime_ready"):
            raise ValueError(f"Старт невозможен: {routing_state.get('runtime_error') or 'маршрутизация не готова'}.")
        if not (
            active_profile
            and active_profile.get("enabled", True)
            and node_can_render_runtime(active_node)
            and self.context.app_paths.generated_xray_config_file.exists()
        ):
            raise ValueError("Старт невозможен: сначала выбери и активируй валидный узел.")
        settings = self.load_settings()
        env = {"ENABLE_FILE_LOGS": "1" if settings["file_logs_enabled"] else "0"}
        result = self.run_shell_action("Подключение", self.context.run_script, env)
        message = "Запуск завершён успешно." if result.ok else f"Запуск завершился ошибкой, код {result.returncode}."
        self.remember_action(result.name, result.ok, message, result.output)
        retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
        return self.collect_status(retention_cleanup=retention_cleanup)

    def stop_runtime(self) -> dict[str, Any]:
        runtime_info = self.inspect_runtime_state()
        if self.runtime_control_blocked(runtime_info):
            raise ValueError(self.runtime_control_guard_message(runtime_info, action="stop"))
        if not runtime_info["has_state"] and not runtime_info["stack_is_live"]:
            self.remember_action("Отключение", True, "Остановка не нужна: подключение уже не активно.", "state=already-stopped")
            retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
            return self.collect_status(retention_cleanup=retention_cleanup)

        result = self.run_shell_action("Отключение", self.context.stop_script)
        message = "Остановка выполнена." if result.ok else f"Остановка завершилась ошибкой, код {result.returncode}."
        self.remember_action(result.name, result.ok, message, result.output)
        retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
        return self.collect_status(retention_cleanup=retention_cleanup)

    def takeover_runtime(self) -> dict[str, Any]:
        runtime_info = self.inspect_runtime_state()
        if runtime_info["ownership"] != "foreign":
            raise ValueError("Перехват доступен только для подключения другой установки.")
        if not runtime_info["has_state"] or not runtime_info["stack_is_live"]:
            raise ValueError("Перехват не нужен: чужое подключение уже не активно.")

        result = self.run_shell_action("Перехват подключения", self.context.stop_script, {"SUBVOST_FORCE_TAKEOVER": "1"})
        message = (
            "Перехват выполнен: чужое подключение остановлено."
            if result.ok
            else f"Перехват завершился ошибкой, код {result.returncode}."
        )
        self.remember_action(result.name, result.ok, message, result.output)
        retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
        return self.collect_status(retention_cleanup=retention_cleanup)

    def capture_diagnostics(self) -> dict[str, Any]:
        result = self.run_shell_action("Диагностика", self.context.diag_script)
        match = re.search(r"(/.+xray-tun-state-[^\s]+\.log)", result.output)
        if result.ok and match:
            message = f"Диагностика сохранена в {match.group(1)}."
        elif result.ok:
            message = "Диагностика снята."
        else:
            message = f"Диагностика завершилась ошибкой, код {result.returncode}."
        self.remember_action(result.name, result.ok, message, result.output)
        retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
        return self.collect_status(retention_cleanup=retention_cleanup)

    def update_xray_core(self) -> dict[str, Any]:
        runtime_info = self.inspect_runtime_state()
        runtime_is_live = any(
            bool(runtime_info.get(key))
            for key in ("stack_is_live", "owned_stack_is_live", "xray_alive", "tun_present")
        )
        if runtime_is_live:
            if runtime_info.get("ownership") == "foreign":
                raise ValueError("Обновление ядра Xray заблокировано: подключением управляет другой экземпляр.")
            if runtime_info.get("ownership") == "unknown":
                raise ValueError("Обновление ядра Xray заблокировано: источник активного подключения не подтверждён.")
            raise ValueError("Обновление ядра Xray заблокировано: сначала отключи активное подключение.")

        result = self.run_shell_action("Обновление ядра Xray", self.context.xray_update_script)
        message = "Ядро Xray обновлено." if result.ok else f"Обновление ядра Xray завершилось ошибкой, код {result.returncode}."
        self.remember_action(result.name, result.ok, message, result.output)
        retention_cleanup = self.cleanup_retained_log_artifacts_from_settings()
        return self.collect_status(retention_cleanup=retention_cleanup)

    def terminate_app(self, source: str = "window-close") -> dict[str, Any]:
        runtime_info = self.inspect_runtime_state()

        if self.runtime_control_blocked(runtime_info):
            message = self.runtime_control_guard_message(runtime_info, action="close")
            self.remember_action("Закрытие приложения", True, message, f"source={source}")
            return {
                "ok": True,
                "message": message,
                "shutdown_source": source,
                "vpn_stop_requested": False,
                "status": self.collect_status(),
            }

        stop_needed = bool(runtime_info["owned_stack_is_live"])
        if stop_needed:
            result = self.run_shell_action("Закрытие приложения", self.context.stop_script)
            if result.ok:
                message = "Приложение закрывается: VPN-подключение остановлено."
            else:
                message = f"Не удалось закрыть приложение: остановка подключения завершилась ошибкой, код {result.returncode}."
            self.remember_action(result.name, result.ok, message, result.output)
            if not result.ok:
                raise ValueError(message)
        else:
            message = "Приложение закрывается: VPN-подключение уже не активно."
            self.remember_action("Закрытие приложения", True, message, f"source={source}")

        return {
            "ok": True,
            "message": message,
            "shutdown_source": source,
            "vpn_stop_requested": stop_needed,
            "status": self.collect_status(),
        }

    def shutdown_gui(self, source: str = "window-close") -> dict[str, Any]:
        message = "Графический интерфейс закрывается без остановки VPN-подключения."
        self.remember_action("Закрытие интерфейса", True, message, f"source={source}")
        return {
            "ok": True,
            "message": message,
            "shutdown_source": source,
            "vpn_stop_requested": False,
            "status": self.collect_status(),
        }
