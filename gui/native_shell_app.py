#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from embedded_webview import ensure_graphical_session
from native_shell_shared import (
    NATIVE_SHELL_APP_ID,
    NATIVE_SHELL_APPINDICATOR_CANDIDATES,
    NATIVE_SHELL_CONTROL_INTERFACE,
    NATIVE_SHELL_CONTROL_OBJECT_PATH,
    NATIVE_SHELL_PAGES,
    NATIVE_SHELL_THEME_LABELS,
    NATIVE_SHELL_THEME_VALUES,
    NATIVE_SHELL_TITLE,
    NATIVE_SHELL_TRAY_ACTIONS,
    NATIVE_SHELL_TRAY_WATCHER_CANDIDATES,
    NativeShellSettings,
    NativeShellTraySupport,
    build_startup_notes,
    build_tray_support,
    native_shell_theme_label,
    should_hide_on_close,
    should_start_hidden,
    tray_action_label,
)
from subvost_paths import build_app_paths, ensure_store_dir
from subvost_store import read_gui_settings, save_gui_settings


GUI_DIR = Path(__file__).resolve().parent
ASSETS_DIR = GUI_DIR.parent / "assets"
ICON_ASSET_PATH = ASSETS_DIR / "subvost-xray-tun-icon.svg"
NATIVE_SHELL_LOG_FILENAME = "native-shell.log"
CONTROL_INTROSPECTION_XML = f"""
<node>
  <interface name="{NATIVE_SHELL_CONTROL_INTERFACE}">
    <method name="ShowWindow" />
    <method name="HideWindow" />
    <method name="OpenSettings" />
    <method name="TriggerAction">
      <arg name="action_id" type="s" direction="in" />
    </method>
    <method name="Quit" />
    <property name="WindowVisible" type="b" access="read" />
    <property name="TrayAvailable" type="b" access="read" />
  </interface>
</node>
""".strip()
DEFAULT_WINDOW_WIDTH = 1100
DEFAULT_WINDOW_HEIGHT = 760
GTK4_WINDOW_CSS = """
window {
  background: linear-gradient(180deg, #f5f2ea 0%, #ebe4d5 100%);
}

.native-shell-root {
  padding: 18px;
  background:
    radial-gradient(circle at top left, rgba(164, 118, 69, 0.18), transparent 32%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(255, 250, 242, 0.92));
}

.native-shell-panel {
  background: rgba(255, 252, 246, 0.92);
  border-radius: 18px;
  border: 1px solid rgba(109, 85, 58, 0.15);
  box-shadow: 0 12px 32px rgba(78, 56, 34, 0.08);
  padding: 20px;
}

.native-shell-muted {
  color: rgba(72, 54, 36, 0.72);
}

.native-shell-status {
  font-weight: 600;
}

.native-shell-page-title {
  font-size: 28px;
  font-weight: 700;
  color: #3f2d1b;
}

.native-shell-card-title {
  font-size: 18px;
  font-weight: 700;
  color: #5f4328;
}
""".strip()


def available_namespace_versions(namespaces: tuple[str, ...]) -> dict[str, set[str]]:
    import gi

    gi.require_version("GIRepository", "2.0")
    repository_module = importlib.import_module("gi.repository.GIRepository")
    repository = repository_module.Repository.get_default()
    return {namespace: set(repository.enumerate_versions(namespace)) for namespace in namespaces}


def list_session_bus_names(gio_module, glib_module) -> set[str]:
    connection = gio_module.bus_get_sync(gio_module.BusType.SESSION, None)
    reply = connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "ListNames",
        None,
        glib_module.VariantType("(as)"),
        gio_module.DBusCallFlags.NONE,
        -1,
        None,
    )
    names, = reply.unpack()
    return set(names)


def probe_tray_support(gio_module, glib_module, *, disable_tray: bool = False) -> NativeShellTraySupport:
    if disable_tray:
        return build_tray_support(watcher_name=None, indicator_candidate=None, error="Tray отключён аргументом запуска.")

    try:
        versions = available_namespace_versions(("Gtk",) + tuple(candidate[0] for candidate in NATIVE_SHELL_APPINDICATOR_CANDIDATES))
    except Exception as exc:
        return build_tray_support(watcher_name=None, indicator_candidate=None, error=f"Не удалось прочитать GI runtime: {exc}")

    if "3.0" not in versions.get("Gtk", set()):
        return build_tray_support(
            watcher_name=None,
            indicator_candidate=None,
            error="Не найден Gtk 3.0 runtime для tray-helper.",
        )

    indicator_candidate = None
    for namespace, version, label in NATIVE_SHELL_APPINDICATOR_CANDIDATES:
        if version in versions.get(namespace, set()):
            indicator_candidate = (namespace, version, label)
            break

    try:
        owned_names = list_session_bus_names(gio_module, glib_module)
    except Exception as exc:
        return build_tray_support(
            watcher_name=None,
            indicator_candidate=indicator_candidate,
            error=f"Не удалось подключиться к session D-Bus: {exc}",
        )

    watcher_name = None
    for candidate in NATIVE_SHELL_TRAY_WATCHER_CANDIDATES:
        if candidate in owned_names:
            watcher_name = candidate
            break
    return build_tray_support(watcher_name=watcher_name, indicator_candidate=indicator_candidate)


def load_gtk4_runtime():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    return Gtk, Gio, GLib, Gdk


def ensure_gtk_display_ready(gtk_module, gdk_module) -> None:
    if not gtk_module.init_check():
        raise RuntimeError("Gtk не смог инициализироваться в текущей графической сессии.")
    if gdk_module.Display.get_default() is None:
        raise RuntimeError("Gtk не видит доступный display, хотя DISPLAY/WAYLAND объявлены.")


def add_css_class(widget, css_class: str) -> None:
    if hasattr(widget, "add_css_class"):
        widget.add_css_class(css_class)


class NativeShellApp:
    def __init__(self, gtk_module, gio_module, glib_module, gdk_module, tray_support: NativeShellTraySupport) -> None:
        self.Gtk = gtk_module
        self.Gio = gio_module
        self.GLib = glib_module
        self.Gdk = gdk_module
        self.tray_support = tray_support
        self.settings_paths = build_app_paths(Path.home())
        ensure_store_dir(self.settings_paths)
        self.settings = NativeShellSettings.from_mapping(read_gui_settings(self.settings_paths))
        self.log_path = self.settings_paths.store_dir / NATIVE_SHELL_LOG_FILENAME
        self.log_lines: list[str] = []
        self.app = self.Gtk.Application(application_id=NATIVE_SHELL_APP_ID, flags=self.Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.settings_window = None
        self.status_label = None
        self.log_buffer = None
        self.control_registration_id = None
        self.control_node_info = self.Gio.DBusNodeInfo.new_for_xml(CONTROL_INTROSPECTION_XML)
        self.tray_process: subprocess.Popen[str] | None = None
        self.allow_close = False
        self.did_initial_activation = False
        self.theme_dropdown = None
        self.settings_switches: dict[str, object] = {}

        self.app.connect("activate", self.on_activate)
        self.app.connect("shutdown", self.on_shutdown)
        self.app.connect("startup", self.on_startup)

    def on_startup(self, app) -> None:
        self.apply_theme_preference(self.settings.theme)
        self.append_log("native-shell", "GTK4 native shell запускается без раннего pkexec.")
        for note in build_startup_notes(self.settings, self.tray_support):
            self.append_log("startup", note)

    def run(self, argv: list[str] | None = None) -> int:
        return self.app.run(argv or sys.argv)

    def on_activate(self, app) -> None:
        if self.window is None:
            self.window = self.build_main_window(app)
            self.register_control_interface()
            self.start_tray_helper_if_needed()

        if not self.did_initial_activation and should_start_hidden(self.settings, self.tray_support):
            self.window.set_visible(False)
            self.did_initial_activation = True
            self.set_status("Приложение запущено в свёрнутом tray-режиме.")
            self.append_log("tray", "Главное окно стартовало скрытым по настройке start minimized to tray.")
            return

        self.did_initial_activation = True
        self.show_window(reason="activate")

    def on_shutdown(self, app) -> None:
        self.stop_tray_helper()
        connection = app.get_dbus_connection()
        if connection is not None and self.control_registration_id is not None:
            connection.unregister_object(self.control_registration_id)
            self.control_registration_id = None

    def register_control_interface(self) -> None:
        if self.control_registration_id is not None:
            return
        connection = self.app.get_dbus_connection()
        if connection is None:
            self.append_log("dbus", "Не удалось получить D-Bus connection для control interface.")
            return
        interface_info = self.control_node_info.interfaces[0]
        self.control_registration_id = connection.register_object(
            NATIVE_SHELL_CONTROL_OBJECT_PATH,
            interface_info,
            self.on_control_method_call,
            self.on_control_get_property,
            None,
        )
        self.append_log("dbus", f"Control interface опубликован по пути {NATIVE_SHELL_CONTROL_OBJECT_PATH}.")

    def on_control_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ) -> None:
        if method_name == "ShowWindow":
            self.show_window(reason="tray")
            invocation.return_value(None)
            return
        if method_name == "HideWindow":
            self.hide_window(reason="tray")
            invocation.return_value(None)
            return
        if method_name == "OpenSettings":
            self.open_settings_window()
            invocation.return_value(None)
            return
        if method_name == "TriggerAction":
            action_id, = parameters.unpack()
            self.trigger_action(action_id, source="tray")
            invocation.return_value(None)
            return
        if method_name == "Quit":
            self.quit_application(source="tray")
            invocation.return_value(None)
            return
        invocation.return_dbus_error(
            f"{NATIVE_SHELL_CONTROL_INTERFACE}.UnsupportedMethod",
            f"Неподдерживаемый метод: {method_name}",
        )

    def on_control_get_property(self, connection, sender, object_path, interface_name, property_name):
        if property_name == "WindowVisible":
            return self.GLib.Variant.new_boolean(self.is_window_visible())
        if property_name == "TrayAvailable":
            return self.GLib.Variant.new_boolean(self.tray_support.available)
        return None

    def build_main_window(self, app):
        window = self.Gtk.ApplicationWindow(application=app)
        window.set_title(NATIVE_SHELL_TITLE)
        window.set_default_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        if hasattr(window, "set_icon_name"):
            window.set_icon_name("network-vpn")
        window.connect("close-request", self.on_close_request)

        display = self.Gdk.Display.get_default()
        provider = self.Gtk.CssProvider()
        provider.load_from_data(GTK4_WINDOW_CSS)
        self.Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=18)
        add_css_class(root, "native-shell-root")
        header = self.build_header_bar()
        status_panel = self.build_status_panel()
        stack = self.build_stack()

        root.append(status_panel)
        root.append(stack)
        window.set_titlebar(header)
        window.set_child(root)
        return window

    def build_header_bar(self):
        header = self.Gtk.HeaderBar()
        header.set_show_title_buttons(True)

        title_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=2)
        title_label = self.Gtk.Label(label="GTK4 Native Shell", xalign=0)
        add_css_class(title_label, "native-shell-card-title")
        subtitle_label = self.Gtk.Label(label="Desktop shell for future runtime integration", xalign=0)
        add_css_class(subtitle_label, "native-shell-muted")
        title_box.append(title_label)
        title_box.append(subtitle_label)
        header.set_title_widget(title_box)

        settings_button = self.Gtk.Button(label="Настройки")
        settings_button.connect("clicked", lambda *_args: self.open_settings_window())
        header.pack_end(settings_button)
        return header

    def build_status_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        add_css_class(panel, "native-shell-panel")

        title_label = self.Gtk.Label(label="Первый реализационный этап native GUI", xalign=0)
        add_css_class(title_label, "native-shell-page-title")
        description_label = self.Gtk.Label(
            label=(
                "Окно, навигация, tray-shell и настройки уже отделены от web GUI. "
                "Backend-команды пока работают как stub и не вызывают pkexec."
            ),
            xalign=0,
        )
        description_label.set_wrap(True)
        add_css_class(description_label, "native-shell-muted")

        self.status_label = self.Gtk.Label(xalign=0)
        self.status_label.set_wrap(True)
        add_css_class(self.status_label, "native-shell-status")
        self.set_status(self.tray_support.reason if not self.tray_support.available else self.tray_support.reason)

        action_box = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        for action_id in ("start-runtime", "stop-runtime", "capture-diagnostics"):
            button = self.Gtk.Button(label=tray_action_label(action_id))
            button.connect("clicked", self.on_stub_button_clicked, action_id)
            action_box.append(button)

        panel.append(title_label)
        panel.append(description_label)
        panel.append(self.status_label)
        panel.append(action_box)
        return panel

    def build_stack(self):
        outer = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=16)
        add_css_class(outer, "native-shell-panel")

        stack = self.Gtk.Stack()
        stack.set_hexpand(True)
        stack.set_vexpand(True)
        stack.set_transition_type(self.Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        sidebar = self.Gtk.StackSidebar()
        sidebar.set_stack(stack)
        sidebar.set_size_request(220, -1)
        outer.append(sidebar)

        for page in NATIVE_SHELL_PAGES:
            stack.add_titled(self.build_page(page), page.page_id, page.title)

        outer.append(stack)
        return outer

    def build_page(self, page):
        page_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=16)
        page_box.set_margin_top(8)
        page_box.set_margin_bottom(8)
        page_box.set_margin_start(8)
        page_box.set_margin_end(8)

        title_label = self.Gtk.Label(label=page.title, xalign=0)
        add_css_class(title_label, "native-shell-page-title")
        text_label = self.Gtk.Label(label=page.description, xalign=0)
        text_label.set_wrap(True)
        add_css_class(text_label, "native-shell-muted")

        page_box.append(title_label)
        page_box.append(text_label)
        if page.page_id == "dashboard":
            page_box.append(self.build_dashboard_page())
        elif page.page_id == "subscriptions":
            page_box.append(self.build_subscriptions_page())
        elif page.page_id == "log":
            page_box.append(self.build_log_page())
        return page_box

    def build_dashboard_page(self):
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(card, "native-shell-panel")
        card_title = self.Gtk.Label(label="Tray / runtime shell status", xalign=0)
        add_css_class(card_title, "native-shell-card-title")
        card.append(card_title)
        lines = [
            f"Tray backend: {self.tray_support.backend_label if self.tray_support.available else 'fallback'}",
            f"Close to tray: {'включено' if self.settings.close_to_tray else 'выключено'}",
            f"Start minimized: {'включено' if self.settings.start_minimized_to_tray else 'выключено'}",
            f"Theme: {native_shell_theme_label(self.settings.theme)}",
        ]
        for line in lines:
            label = self.Gtk.Label(label=line, xalign=0)
            add_css_class(label, "native-shell-muted")
            card.append(label)
        return card

    def build_subscriptions_page(self):
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(card, "native-shell-panel")
        card_title = self.Gtk.Label(label="Subscriptions placeholder", xalign=0)
        add_css_class(card_title, "native-shell-card-title")
        body = self.Gtk.Label(
            label=(
                "Здесь появится импорт подписок, список профилей и активных узлов. "
                "На этапе 0053.1 страница подтверждает только будущую навигационную структуру."
            ),
            xalign=0,
        )
        body.set_wrap(True)
        add_css_class(body, "native-shell-muted")
        card.append(card_title)
        card.append(body)
        return card

    def build_log_page(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(container, "native-shell-panel")
        title = self.Gtk.Label(label="Shell log", xalign=0)
        add_css_class(title, "native-shell-card-title")
        scrolled = self.Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        text_view = self.Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        self.log_buffer = text_view.get_buffer()
        self.refresh_log_view()
        scrolled.set_child(text_view)
        container.append(title)
        container.append(scrolled)
        return container

    def build_settings_window(self):
        window = self.Gtk.Window(transient_for=self.window, title="Настройки native shell")
        window.set_default_size(540, 420)
        window.set_modal(False)

        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)
        add_css_class(root, "native-shell-root")

        intro = self.Gtk.Label(
            label=(
                "Минимальная оболочка настроек для v1. Здесь сохраняются только shell-параметры, "
                "без сетевых, runtime и routing-настроек."
            ),
            xalign=0,
        )
        intro.set_wrap(True)
        add_css_class(intro, "native-shell-muted")
        root.append(intro)

        switches = (
            ("file_logs_enabled", "Файловое логирование", "Сохранять журнал native shell в пользовательском store-каталоге."),
            ("close_to_tray", "Закрытие окна уводит в tray", "Используется только если tray backend реально доступен."),
            ("start_minimized_to_tray", "Старт свёрнутым в tray", "Если tray недоступен, окно всё равно откроется обычным способом."),
        )

        for key, title, subtitle in switches:
            row, switch = self.build_switch_row(title, subtitle, getattr(self.settings, key))
            switch.connect("notify::active", self.on_settings_switch_changed, key)
            self.settings_switches[key] = switch
            root.append(row)

        theme_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        theme_title = self.Gtk.Label(label="Тема окна", xalign=0)
        add_css_class(theme_title, "native-shell-card-title")
        theme_hint = self.Gtk.Label(
            label="Для GTK4 shell сейчас поддерживается системный режим и тёмная тема через `gtk-application-prefer-dark-theme`.",
            xalign=0,
        )
        theme_hint.set_wrap(True)
        add_css_class(theme_hint, "native-shell-muted")
        theme_model = self.Gtk.StringList.new([NATIVE_SHELL_THEME_LABELS[value] for value in NATIVE_SHELL_THEME_VALUES])
        self.theme_dropdown = self.Gtk.DropDown(model=theme_model)
        self.theme_dropdown.set_selected(NATIVE_SHELL_THEME_VALUES.index(self.settings.theme))
        self.theme_dropdown.connect("notify::selected", self.on_theme_changed)
        theme_box.append(theme_title)
        theme_box.append(theme_hint)
        theme_box.append(self.theme_dropdown)
        root.append(theme_box)

        tray_note = self.Gtk.Label(
            label=f"Состояние tray backend: {self.tray_support.reason}",
            xalign=0,
        )
        tray_note.set_wrap(True)
        add_css_class(tray_note, "native-shell-muted")
        root.append(tray_note)

        log_path_label = self.Gtk.Label(label=f"Локальный лог: {self.log_path}", xalign=0)
        log_path_label.set_wrap(True)
        add_css_class(log_path_label, "native-shell-muted")
        root.append(log_path_label)

        close_button = self.Gtk.Button(label="Закрыть")
        close_button.connect("clicked", lambda *_args: window.hide())
        root.append(close_button)

        window.set_child(root)
        return window

    def build_switch_row(self, title: str, subtitle: str, active: bool):
        row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=12)
        text_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=2)
        title_label = self.Gtk.Label(label=title, xalign=0)
        add_css_class(title_label, "native-shell-card-title")
        subtitle_label = self.Gtk.Label(label=subtitle, xalign=0)
        subtitle_label.set_wrap(True)
        add_css_class(subtitle_label, "native-shell-muted")
        switch = self.Gtk.Switch(active=active)
        switch.set_halign(self.Gtk.Align.END)
        switch.set_valign(self.Gtk.Align.CENTER)
        text_box.append(title_label)
        text_box.append(subtitle_label)
        row.append(text_box)
        row.append(switch)
        return row, switch

    def on_stub_button_clicked(self, _button, action_id: str) -> None:
        self.trigger_action(action_id, source="window")

    def trigger_action(self, action_id: str, *, source: str) -> None:
        if action_id == "show-window":
            self.show_window(reason=source)
            return
        if action_id == "hide-window":
            self.hide_window(reason=source)
            return
        if action_id == "open-settings":
            self.open_settings_window()
            return
        if action_id == "quit-app":
            self.quit_application(source=source)
            return

        action_label = tray_action_label(action_id)
        self.set_status(f"{action_label}: backend-интеграция ещё не подключена.")
        self.append_log(source, f"{action_label}: выполнен shell-stub без вызова pkexec.")

    def show_window(self, *, reason: str) -> None:
        if self.window is None:
            return
        self.window.present()
        self.set_status("Главное окно показано.")
        self.append_log(reason, "Главное окно показано.")

    def hide_window(self, *, reason: str) -> None:
        if self.window is None:
            return
        if not self.tray_support.available:
            self.set_status("Tray недоступен: окно нельзя безопасно спрятать.")
            self.append_log(reason, "Скрытие окна пропущено: tray backend недоступен.")
            return
        self.window.set_visible(False)
        self.set_status("Окно скрыто, приложение остаётся доступным через tray.")
        self.append_log(reason, "Главное окно скрыто и оставлено работать в фоне.")

    def open_settings_window(self) -> None:
        if self.settings_window is None:
            self.settings_window = self.build_settings_window()
        self.settings_window.present()
        self.append_log("settings", "Открыто окно настроек native shell.")

    def on_close_request(self, *_args):
        if should_hide_on_close(self.settings, self.tray_support) and not self.allow_close:
            self.hide_window(reason="close-request")
            return True
        return False

    def on_settings_switch_changed(self, switch, _param_spec, key: str) -> None:
        value = bool(switch.get_active())
        setattr(self.settings, key, value)
        self.persist_settings()
        if key == "close_to_tray":
            self.append_log("settings", f"Настройка close_to_tray изменена: {int(value)}.")
        elif key == "start_minimized_to_tray":
            self.append_log("settings", f"Настройка start_minimized_to_tray изменена: {int(value)}.")
        elif key == "file_logs_enabled":
            self.append_log("settings", f"Настройка file_logs_enabled изменена: {int(value)}.")
        self.refresh_status_after_settings_change()

    def on_theme_changed(self, dropdown, _param_spec) -> None:
        theme = NATIVE_SHELL_THEME_VALUES[dropdown.get_selected()]
        self.settings.theme = theme
        self.apply_theme_preference(theme)
        self.persist_settings()
        self.append_log("settings", f"Theme изменена: {native_shell_theme_label(theme)}.")
        self.refresh_status_after_settings_change()

    def refresh_status_after_settings_change(self) -> None:
        if self.tray_support.available:
            self.set_status(
                "Настройки shell сохранены. "
                f"Close to tray: {'on' if self.settings.close_to_tray else 'off'}, "
                f"start minimized: {'on' if self.settings.start_minimized_to_tray else 'off'}."
            )
            return
        self.set_status(f"Настройки shell сохранены. Tray fallback: {self.tray_support.reason}")

    def persist_settings(self) -> None:
        save_gui_settings(
            self.settings_paths,
            self.settings.file_logs_enabled,
            close_to_tray=self.settings.close_to_tray,
            start_minimized_to_tray=self.settings.start_minimized_to_tray,
            theme=self.settings.theme,
        )

    def apply_theme_preference(self, theme: str) -> None:
        settings = self.Gtk.Settings.get_default()
        if settings is None:
            return
        try:
            settings.set_property("gtk-application-prefer-dark-theme", theme == "dark")
        except (TypeError, ValueError):
            return

    def append_log(self, source: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{source}] {message}"
        self.log_lines.append(line)
        self.log_lines = self.log_lines[-200:]
        if self.settings.file_logs_enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        self.refresh_log_view()

    def refresh_log_view(self) -> None:
        if self.log_buffer is None:
            return
        self.log_buffer.set_text("\n".join(self.log_lines))

    def set_status(self, message: str) -> None:
        if self.status_label is not None:
            self.status_label.set_label(message)

    def is_window_visible(self) -> bool:
        return bool(self.window is not None and self.window.get_visible())

    def start_tray_helper_if_needed(self) -> None:
        if not self.tray_support.available:
            self.append_log("tray", f"Tray helper не запущен: {self.tray_support.reason}")
            return
        helper_path = GUI_DIR / "native_shell_tray_helper.py"
        command = [
            sys.executable,
            str(helper_path),
            "--control-bus-name",
            NATIVE_SHELL_APP_ID,
            "--control-object-path",
            NATIVE_SHELL_CONTROL_OBJECT_PATH,
            "--indicator-namespace",
            self.tray_support.indicator_namespace or "AyatanaAppIndicator3",
            "--icon-name",
            "network-vpn",
        ]
        self.tray_process = subprocess.Popen(
            command,
            cwd=str(GUI_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.append_log("tray", f"Tray helper запущен через backend {self.tray_support.backend_label}.")
        self.GLib.timeout_add(700, self.verify_tray_helper_started)
        self.GLib.timeout_add_seconds(5, self.poll_tray_helper)

    def verify_tray_helper_started(self) -> bool:
        if self.tray_process is None:
            return False
        return_code = self.tray_process.poll()
        if return_code is None:
            return False
        self.tray_support = build_tray_support(
            watcher_name=None,
            indicator_candidate=None,
            error=f"Tray helper завершился с кодом {return_code}.",
        )
        self.append_log("tray", self.tray_support.reason)
        self.refresh_status_after_settings_change()
        return False

    def poll_tray_helper(self) -> bool:
        if self.tray_process is None:
            return False
        return_code = self.tray_process.poll()
        if return_code is None:
            return True
        self.tray_support = build_tray_support(
            watcher_name=None,
            indicator_candidate=None,
            error=f"Tray helper остановился с кодом {return_code}.",
        )
        self.append_log("tray", self.tray_support.reason)
        self.refresh_status_after_settings_change()
        self.tray_process = None
        return False

    def stop_tray_helper(self) -> None:
        if self.tray_process is None:
            return
        if self.tray_process.poll() is None:
            self.tray_process.terminate()
            try:
                self.tray_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.tray_process.kill()
        self.tray_process = None

    def quit_application(self, *, source: str) -> None:
        self.allow_close = True
        self.append_log(source, "Приложение завершает работу по команде shell/tray.")
        self.app.quit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GTK4 native shell prototype for Subvost Xray TUN.")
    parser.add_argument(
        "--disable-tray",
        action="store_true",
        help="Принудительно отключить tray backend и проверить fallback-поведение.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_graphical_session()
    gtk_module, gio_module, glib_module, gdk_module = load_gtk4_runtime()
    ensure_gtk_display_ready(gtk_module, gdk_module)
    tray_support = probe_tray_support(gio_module, glib_module, disable_tray=args.disable_tray)
    app = NativeShellApp(gtk_module, gio_module, glib_module, gdk_module, tray_support)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
