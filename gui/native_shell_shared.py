from __future__ import annotations

from dataclasses import dataclass
from typing import Any


NATIVE_SHELL_APP_ID = "io.subvost.XrayTunNativeShell"
NATIVE_SHELL_TITLE = "Subvost Xray TUN Native Shell"
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
    NATIVE_SHELL_THEME_SYSTEM,
    NATIVE_SHELL_THEME_LIGHT,
    NATIVE_SHELL_THEME_DARK,
)
NATIVE_SHELL_THEME_LABELS = {
    NATIVE_SHELL_THEME_SYSTEM: "Системная",
    NATIVE_SHELL_THEME_LIGHT: "Светлая",
    NATIVE_SHELL_THEME_DARK: "Тёмная",
}
NATIVE_SHELL_STORE_ACTION_LABELS = {
    "subscriptions-add": "Добавление подписки",
    "subscriptions-refresh-all": "Обновить все подписки",
    "subscription-refresh": "Обновление подписки",
    "subscription-toggle": "Состояние подписки",
    "subscription-delete": "Удаление подписки",
    "node-activate": "Активация узла",
    "node-ping": "Ping узла",
    "routing-import": "Импорт маршрутизации",
    "routing-toggle": "Master toggle маршрутизации",
    "routing-clear-active": "Сброс маршрутизации",
    "routing-activate-profile": "Активация маршрутизации",
    "routing-toggle-profile": "Состояние routing-профиля",
}

@dataclass(frozen=True)
class NativeShellPage:
    page_id: str
    title: str
    description: str


NATIVE_SHELL_PAGES = (
    NativeShellPage(
        "dashboard",
        "Dashboard",
        "Главная operational-плоскость: runtime-статус, метрики, ownership и действия `Старт / Стоп / Диагностика`.",
    ),
    NativeShellPage(
        "subscriptions",
        "Subscriptions",
        "Рабочий экран подписок: URL-импорт, список узлов, отдельный ping и routing-профили.",
    ),
    NativeShellPage(
        "log",
        "Log",
        "Локальный журнал native shell и результаты runtime-действий этого окна.",
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
    NativeShellTrayAction("start-runtime", "Старт", "Запустить runtime bundle через общий service-layer и `pkexec`."),
    NativeShellTrayAction("stop-runtime", "Стоп", "Остановить текущий runtime bundle через общий service-layer."),
    NativeShellTrayAction("capture-diagnostics", "Снять диагностику", "Собрать диагностический дамп bundle через общий service-layer."),
    NativeShellTrayAction("open-settings", "Настройки", "Открыть минимальное окно настроек shell-уровня."),
    NativeShellTrayAction("quit-app", "Выход", "Полностью завершить native shell."),
)


@dataclass
class NativeShellSettings:
    file_logs_enabled: bool = False
    close_to_tray: bool = False
    start_minimized_to_tray: bool = False
    theme: str = NATIVE_SHELL_THEME_SYSTEM

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
    candidate = str(value or "").strip().lower()
    if candidate in NATIVE_SHELL_THEME_VALUES:
        return candidate
    return NATIVE_SHELL_THEME_SYSTEM


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
    return NATIVE_SHELL_STORE_ACTION_LABELS.get(action_id, action_id)


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
            "Не найден GI runtime для Ayatana/AppIndicator.",
        )
    namespace, _, label = indicator_candidate
    return NativeShellTraySupport(
        True,
        label,
        f"Tray backend активирован через {label}.",
        watcher_name=watcher_name,
        indicator_namespace=namespace,
    )


def build_startup_notes(settings: NativeShellSettings, tray_support: NativeShellTraySupport) -> list[str]:
    notes = [
        f"Theme: {native_shell_theme_label(settings.theme)}.",
        "Файловые логи: включены." if settings.file_logs_enabled else "Файловые логи: выключены.",
    ]
    if tray_support.available:
        notes.append(f"Tray backend: {tray_support.backend_label}.")
        if settings.start_minimized_to_tray:
            notes.append("Старт выполнен в свёрнутом режиме.")
        if settings.close_to_tray:
            notes.append("Закрытие окна уводит приложение в трей.")
    else:
        notes.append(f"Tray fallback: {tray_support.reason}")
        if settings.start_minimized_to_tray:
            notes.append("Опция старта в tray сохранена, но сейчас окно откроется обычно.")
        if settings.close_to_tray:
            notes.append("Опция close-to-tray сохранена, но без трея окно будет закрываться полностью.")
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
