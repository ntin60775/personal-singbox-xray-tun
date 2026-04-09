from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class NativeShellPage:
    page_id: str
    title: str
    description: str


NATIVE_SHELL_PAGES = (
    NativeShellPage(
        "dashboard",
        "Dashboard",
        "Главная точка управления runtime. На этом этапе здесь только оболочка и stub-действия.",
    ),
    NativeShellPage(
        "subscriptions",
        "Subscriptions",
        "Раздел под будущий импорт подписок, выбор профилей и управление узлами.",
    ),
    NativeShellPage(
        "log",
        "Log",
        "Временный журнал native shell: здесь видны tray-события, настройки и stub-команды.",
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
    NativeShellTrayAction("start-runtime", "Старт", "Stub-действие для будущего запуска runtime."),
    NativeShellTrayAction("stop-runtime", "Стоп", "Stub-действие для будущей остановки runtime."),
    NativeShellTrayAction("capture-diagnostics", "Снять диагностику", "Stub-действие для будущего диагностического дампа."),
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
