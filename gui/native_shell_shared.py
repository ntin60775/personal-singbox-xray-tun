from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


NATIVE_SHELL_APP_ID = "io.subvost.XrayTunNativeShell"
NATIVE_SHELL_TITLE = "Subvost Xray TUN"
NATIVE_SHELL_CONTROL_INTERFACE = "io.subvost.XrayTunNativeShell.Control"
NATIVE_SHELL_CONTROL_OBJECT_PATH = "/io/subvost/XrayTunNativeShell/Control"
NATIVE_SHELL_TRAY_WATCHER_CANDIDATES = (
    "org.kde.StatusNotifierWatcher",
    "org.freedesktop.StatusNotifierWatcher",
)
NATIVE_SHELL_APPINDICATOR_CANDIDATES = (
    ("AyatanaAppIndicator3", "0.1", "Ayatana AppIndicator"),
    ("AppIndicator3", "0.1", "AppIndicator"),
)
NATIVE_SHELL_THEME_SYSTEM = "system"
NATIVE_SHELL_THEME_LIGHT = "light"
NATIVE_SHELL_THEME_DARK = "dark"
NATIVE_SHELL_THEME_VALUES = (
    NATIVE_SHELL_THEME_DARK,
)
NATIVE_SHELL_THEME_LABELS = {
    NATIVE_SHELL_THEME_DARK: "Тёмная",
}
NATIVE_SHELL_STORE_ACTION_LABELS = {
    "subscriptions-add": "Добавление подписки",
    "subscriptions-refresh-all": "Обновить все подписки",
    "subscription-refresh": "Обновление подписки",
    "subscription-toggle": "Состояние подписки",
    "subscription-delete": "Удаление подписки",
    "node-activate": "Активация узла",
    "node-ping": "Проверка узла",
    "routing-import": "Импорт маршрутизации",
    "routing-toggle": "Переключение маршрутизации",
    "routing-clear-active": "Сброс маршрутизации",
    "routing-activate-profile": "Активация маршрутизации",
    "routing-toggle-profile": "Состояние профиля маршрутизации",
}
NATIVE_SHELL_LOG_FILTER_VALUES = (
    "all",
    "error",
    "warning",
    "info",
)
NATIVE_SHELL_LOG_FILTER_LABELS = {
    "all": "Все",
    "error": "Ошибки",
    "warning": "Предупреждения",
    "info": "Инфо",
}
NATIVE_SHELL_LOG_LEVEL_LABELS = {
    "error": "Ошибка",
    "warning": "Предупреждение",
    "info": "Событие",
}
NATIVE_SHELL_LOG_SOURCE_LABELS = {
    "shell": "Оболочка интерфейса",
    "action": "Действие подключения",
    "file": "Журнал подключения",
}
NATIVE_SHELL_LOG_NAME_LABELS = {
    "system": "Система",
    "native-shell": "Нативная оболочка",
    "startup": "Запуск интерфейса",
    "initial-load": "Первичное состояние",
    "tray": "Трей",
    "tray-degraded": "Трей",
    "dbus": "Управляющий канал",
    "subscriptions": "Подписки",
    "routing": "Маршрутизация",
    "status": "Состояние подключения",
    "settings": "Настройки",
    "settings-change": "Настройки",
    "log": "Журнал",
    "window": "Окно",
}


@dataclass(frozen=True)
class NativeShellPage:
    page_id: str
    title: str
    icon_name: str
    description: str


NATIVE_SHELL_PAGES = (
    NativeShellPage(
        "dashboard",
        "Подключение",
        "network-wireless-symbolic",
        "Главный экран: состояние подключения, выбранный узел и действия `Подключиться / Отключить / Диагностика`.",
    ),
    NativeShellPage(
        "subscriptions",
        "Подписки",
        "view-list-symbolic",
        "Управление подписками и правилами маршрутизации в одном экране.",
    ),
    NativeShellPage(
        "log",
        "Диагностика",
        "utilities-terminal-symbolic",
        "Конфликт экземпляров, служебные файлы подключения и журнал действий в одном экране.",
    ),
)


@dataclass(frozen=True)
class NativeShellTrayAction:
    action_id: str
    label: str
    description: str


NATIVE_SHELL_TRAY_ACTIONS = (
    NativeShellTrayAction("show-window", "Показать окно", "Показать главное окно приложения."),
    NativeShellTrayAction("hide-window", "Скрыть окно", "Спрятать окно, не завершая приложение."),
    NativeShellTrayAction("start-runtime", "Подключить", "Запустить подключение через общий сервисный слой и `pkexec`."),
    NativeShellTrayAction("stop-runtime", "Отключить", "Остановить текущее подключение через общий сервисный слой."),
    NativeShellTrayAction("capture-diagnostics", "Снять диагностику", "Собрать диагностический дамп через общий сервисный слой."),
    NativeShellTrayAction("open-settings", "Настройки", "Открыть минимальное окно настроек уровня интерфейса."),
    NativeShellTrayAction("quit-app", "Выход", "Полностью завершить интерфейс приложения."),
)
NATIVE_SHELL_RUNTIME_ACTION_LABELS = {
    "takeover-runtime": "Перехватить подключение",
}


@dataclass
class NativeShellSettings:
    file_logs_enabled: bool = False
    close_to_tray: bool = False
    start_minimized_to_tray: bool = False
    theme: str = NATIVE_SHELL_THEME_DARK

    @classmethod
    def from_mapping(cls, payload: dict[str, object] | None) -> "NativeShellSettings":
        raw = payload or {}
        return cls(
            file_logs_enabled=bool(raw.get("file_logs_enabled", False)),
            close_to_tray=bool(raw.get("close_to_tray", False)),
            start_minimized_to_tray=bool(raw.get("start_minimized_to_tray", False)),
            theme=normalize_native_shell_theme(raw.get("theme")),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "file_logs_enabled": self.file_logs_enabled,
            "close_to_tray": self.close_to_tray,
            "start_minimized_to_tray": self.start_minimized_to_tray,
            "theme": self.theme,
        }


@dataclass(frozen=True)
class NativeShellTraySupport:
    available: bool
    backend_label: str
    reason: str
    watcher_name: str | None = None
    indicator_namespace: str | None = None


def normalize_native_shell_theme(value: object) -> str:
    _ = value
    return NATIVE_SHELL_THEME_DARK


def native_shell_theme_label(theme: str) -> str:
    return NATIVE_SHELL_THEME_LABELS[normalize_native_shell_theme(theme)]


def should_start_hidden(settings: NativeShellSettings, tray_support: NativeShellTraySupport) -> bool:
    return settings.start_minimized_to_tray and tray_support.available


def should_hide_on_close(settings: NativeShellSettings, tray_support: NativeShellTraySupport) -> bool:
    return settings.close_to_tray and tray_support.available


def tray_action_label(action_id: str) -> str:
    for action in NATIVE_SHELL_TRAY_ACTIONS:
        if action.action_id == action_id:
            return action.label
    return action_id


def native_shell_action_label(action_id: str) -> str:
    tray_label = tray_action_label(action_id)
    if tray_label != action_id:
        return tray_label
    if action_id in NATIVE_SHELL_RUNTIME_ACTION_LABELS:
        return NATIVE_SHELL_RUNTIME_ACTION_LABELS[action_id]
    return NATIVE_SHELL_STORE_ACTION_LABELS.get(action_id, action_id)


def normalize_native_shell_log_filter(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in NATIVE_SHELL_LOG_FILTER_VALUES:
        return candidate
    return "all"


def native_shell_log_filter_label(value: object) -> str:
    return NATIVE_SHELL_LOG_FILTER_LABELS[normalize_native_shell_log_filter(value)]


def native_shell_log_level_label(value: object) -> str:
    candidate = str(value or "info").strip().lower() or "info"
    return NATIVE_SHELL_LOG_LEVEL_LABELS.get(candidate, NATIVE_SHELL_LOG_LEVEL_LABELS["info"])


def native_shell_log_source_label(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in NATIVE_SHELL_LOG_SOURCE_LABELS:
        return NATIVE_SHELL_LOG_SOURCE_LABELS[candidate]
    if candidate:
        return candidate
    return "система"


def native_shell_log_name_label(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in NATIVE_SHELL_LOG_NAME_LABELS:
        return NATIVE_SHELL_LOG_NAME_LABELS[candidate]
    if candidate:
        return str(value).strip()
    return "Система"


def select_indicator_candidate(versions_by_namespace: dict[str, set[str]] | None = None) -> tuple[str, str, str] | None:
    for namespace, version, label in NATIVE_SHELL_APPINDICATOR_CANDIDATES:
        if versions_by_namespace is None:
            return namespace, version, label
        if version in versions_by_namespace.get(namespace, set()):
            return namespace, version, label
    return None


def select_status_notifier_watcher(owned_names: set[str] | None) -> str | None:
    if not owned_names:
        return None
    for watcher_name in NATIVE_SHELL_TRAY_WATCHER_CANDIDATES:
        if watcher_name in owned_names:
            return watcher_name
    return None


def build_tray_support(
    *,
    watcher_name: str | None,
    indicator_candidate: tuple[str, str, str] | None,
    error: str = "",
) -> NativeShellTraySupport:
    if error:
        return NativeShellTraySupport(False, "fallback", error)
    if not watcher_name:
        return NativeShellTraySupport(
            False,
            "fallback",
            "В сессии не найден совместимый status notifier watcher.",
        )
    if indicator_candidate is None:
        return NativeShellTraySupport(
            False,
            "fallback",
            "Не найдено GI-окружение для Ayatana/AppIndicator.",
        )
    namespace, _, label = indicator_candidate
    return NativeShellTraySupport(
        True,
        label,
        f"Трей активирован через {label}.",
        watcher_name=watcher_name,
        indicator_namespace=namespace,
    )


def build_startup_notes(settings: NativeShellSettings, tray_support: NativeShellTraySupport) -> list[str]:
    notes = [
        f"Тема: {native_shell_theme_label(settings.theme)}.",
        "Файловые логи: включены." if settings.file_logs_enabled else "Файловые логи: выключены.",
    ]
    if tray_support.available:
        notes.append(f"Трей: {tray_support.backend_label}.")
        if settings.start_minimized_to_tray:
            notes.append("Старт выполнен в свёрнутом режиме.")
        if settings.close_to_tray:
            notes.append("Закрытие окна уводит приложение в трей.")
    else:
        notes.append(f"Трей недоступен: {tray_support.reason}")
        if settings.start_minimized_to_tray:
            notes.append("Опция старта в трее сохранена, но сейчас окно откроется обычно.")
        if settings.close_to_tray:
            notes.append("Опция сворачивания в трей сохранена, но без трея окно будет закрываться полностью.")
    return notes


def store_snapshot_container(store_payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = store_payload or {}
    store = payload.get("store")
    return store if isinstance(store, dict) else {}


def subscriptions_from_store_snapshot(store_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    store = store_snapshot_container(store_payload)
    subscriptions = store.get("subscriptions")
    return subscriptions if isinstance(subscriptions, list) else []


def profiles_from_store_snapshot(store_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    store = store_snapshot_container(store_payload)
    profiles = store.get("profiles")
    return profiles if isinstance(profiles, list) else []


def routing_from_store_snapshot(store_payload: dict[str, Any] | None) -> dict[str, Any]:
    store = store_snapshot_container(store_payload)
    routing = store.get("routing")
    return routing if isinstance(routing, dict) else {}


def routing_profiles_from_store_snapshot(store_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    profiles = routing_from_store_snapshot(store_payload).get("profiles")
    return profiles if isinstance(profiles, list) else []


def active_profile_from_store_snapshot(store_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = store_payload or {}
    active_profile = payload.get("active_profile")
    return active_profile if isinstance(active_profile, dict) else None


def active_node_from_store_snapshot(store_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = store_payload or {}
    active_node = payload.get("active_node")
    return active_node if isinstance(active_node, dict) else None


def active_routing_profile_from_store_snapshot(store_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    payload = store_payload or {}
    active_profile = payload.get("active_routing_profile")
    return active_profile if isinstance(active_profile, dict) else None


def log_entries_from_status(status_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    payload = status_payload or {}
    logs_payload = payload.get("logs")
    if not isinstance(logs_payload, dict):
        return []
    entries = logs_payload.get("entries")
    return entries if isinstance(entries, list) else []


def filter_log_entries(entries: list[dict[str, Any]] | None, level_filter: object) -> list[dict[str, Any]]:
    normalized_filter = normalize_native_shell_log_filter(level_filter)
    result: list[dict[str, Any]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        level = str(entry.get("level") or "info").strip().lower() or "info"
        if normalized_filter == "all" or level == normalized_filter:
            result.append(entry)
    return result


def format_native_shell_log_timestamp(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "без времени"
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw.replace("T", " ")


def format_native_shell_log_entry(entry: dict[str, Any]) -> str:
    timestamp = format_native_shell_log_timestamp(entry.get("timestamp"))
    level_label = native_shell_log_level_label(entry.get("level"))
    source_label = native_shell_log_source_label(entry.get("source"))
    name = native_shell_log_name_label(entry.get("name"))
    message = str(entry.get("message") or "").strip() or "Сообщение отсутствует."
    lines = [
        f"{timestamp} | {level_label} | {source_label} | {name}",
        message,
    ]
    details = str(entry.get("details") or "").strip()
    if details:
        lines.extend(f"> {line}" if line else ">" for line in details.splitlines())
    return "\n".join(lines)


def build_native_shell_log_text(
    *,
    bundle_entries: list[dict[str, Any]] | None,
    shell_entries: list[dict[str, Any]] | None,
    level_filter: object,
) -> str:
    normalized_filter = normalize_native_shell_log_filter(level_filter)
    filtered_shell = filter_log_entries(shell_entries, normalized_filter)
    filtered_bundle = filter_log_entries(bundle_entries, normalized_filter)
    sections = [
        ("Оболочка интерфейса", filtered_shell),
        ("Подключение и служебный журнал", filtered_bundle),
    ]
    chunks = [f"Фильтр: {native_shell_log_filter_label(normalized_filter)}"]
    for title, entries in sections:
        chunks.append("")
        chunks.append(f"=== {title} ({len(entries)}) ===")
        if not entries:
            chunks.append("нет записей")
            continue
        for entry in entries:
            chunks.append(format_native_shell_log_entry(entry))
            chunks.append("")
        if chunks[-1] == "":
            chunks.pop()
    return "\n".join(chunks).strip()


def latest_error_from_log_entries(entries: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    latest_entry: dict[str, Any] | None = None
    latest_key: tuple[int, str, int] | None = None
    for index, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        level = str(entry.get("level") or "info").strip().lower() or "info"
        if level != "error":
            continue
        timestamp = str(entry.get("timestamp") or "").strip()
        sort_key = (1 if timestamp else 0, timestamp, index)
        if latest_key is None or sort_key > latest_key:
            latest_key = sort_key
            latest_entry = entry
    return latest_entry


def resolve_selected_subscription_id(
    store_payload: dict[str, Any] | None,
    current_selected_id: str | None,
) -> str | None:
    subscriptions = subscriptions_from_store_snapshot(store_payload)
    if not subscriptions:
        return None

    subscription_ids = {str(item.get("id")) for item in subscriptions if item.get("id")}
    if current_selected_id and current_selected_id in subscription_ids:
        return current_selected_id

    active_profile = active_profile_from_store_snapshot(store_payload)
    active_subscription_id = str(active_profile.get("source_subscription_id") or "") if active_profile else ""
    if active_subscription_id and active_subscription_id in subscription_ids:
        return active_subscription_id

    first_subscription_id = subscriptions[0].get("id")
    return str(first_subscription_id) if first_subscription_id else None


def selected_subscription_from_store_snapshot(
    store_payload: dict[str, Any] | None,
    selected_subscription_id: str | None,
) -> dict[str, Any] | None:
    resolved_id = resolve_selected_subscription_id(store_payload, selected_subscription_id)
    if not resolved_id:
        return None
    for subscription in subscriptions_from_store_snapshot(store_payload):
        if str(subscription.get("id")) == resolved_id:
            return subscription
    return None


def selected_profile_from_store_snapshot(
    store_payload: dict[str, Any] | None,
    selected_subscription_id: str | None,
) -> dict[str, Any] | None:
    subscription = selected_subscription_from_store_snapshot(store_payload, selected_subscription_id)
    if not subscription:
        return None
    profile_id = str(subscription.get("profile_id") or "")
    if not profile_id:
        return None
    for profile in profiles_from_store_snapshot(store_payload):
        if str(profile.get("id")) == profile_id:
            return profile
    return None


def ping_snapshot_from_status(
    status_payload: dict[str, Any] | None,
    profile_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    payload = status_payload or {}
    ping = payload.get("ping")
    if not isinstance(ping, dict):
        return None
    cache = ping.get("cache")
    if not isinstance(cache, dict):
        return None
    snapshot = cache.get(f"{profile_id}:{node_id}")
    return snapshot if isinstance(snapshot, dict) else None
