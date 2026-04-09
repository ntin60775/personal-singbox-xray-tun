#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

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
from subvost_app_service import ServiceState, SubvostAppService, build_default_service


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
@define-color app_bg #101218;
@define-color window_bg #151821;
@define-color panel_bg #1B1F2A;
@define-color elevated_bg #222735;
@define-color hover_bg #2A3040;
@define-color border_subtle #2B3140;
@define-color border_strong #3A4256;
@define-color text_primary #F3F6FB;
@define-color text_secondary #B7C0D4;
@define-color text_muted #8D96AA;
@define-color accent_primary #FF6363;
@define-color accent_primary_hover #FF7474;
@define-color accent_primary_soft rgba(255, 99, 99, 0.16);
@define-color state_success #3DDC97;
@define-color state_warning #FFB84D;
@define-color state_error #FF5D73;
@define-color state_info #7BC4FF;

window {
  color: @text_primary;
  background:
    radial-gradient(circle at top left, rgba(123, 196, 255, 0.10), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 99, 99, 0.10), transparent 24%),
    linear-gradient(180deg, @app_bg 0%, #0d1016 100%);
}

.native-shell-root {
  color: @text_primary;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(255, 99, 99, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(21, 24, 33, 0.96), rgba(16, 18, 24, 0.98));
}

.native-shell-panel {
  background: rgba(27, 31, 42, 0.92);
  border-radius: 18px;
  border: 1px solid rgba(58, 66, 86, 0.72);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
  padding: 20px;
}

.native-shell-muted {
  color: @text_muted;
}

.native-shell-status {
  color: @text_secondary;
  font-weight: 600;
}

.native-shell-page-title {
  color: @text_primary;
  font-size: 26px;
  font-weight: 700;
}

.native-shell-card-title {
  color: @text_primary;
  font-size: 17px;
  font-weight: 700;
}

.native-shell-card-subtitle {
  color: @text_secondary;
  font-size: 13px;
}

.native-shell-hero {
  background:
    linear-gradient(180deg, rgba(34, 39, 53, 0.96), rgba(27, 31, 42, 0.92)),
    radial-gradient(circle at top right, rgba(255, 99, 99, 0.16), transparent 38%);
}

.native-shell-value {
  color: @text_primary;
  font-size: 20px;
  font-weight: 700;
}

.native-shell-value-large {
  color: @text_primary;
  font-size: 30px;
  font-weight: 700;
}

.native-shell-value-muted {
  color: @text_secondary;
}

.native-shell-badge {
  background: rgba(34, 39, 53, 0.96);
  border-radius: 999px;
  border: 1px solid rgba(58, 66, 86, 0.92);
  padding: 6px 10px;
  color: @text_secondary;
  font-size: 12px;
}

.native-shell-badge-running {
  background: rgba(61, 220, 151, 0.18);
  border-color: rgba(61, 220, 151, 0.45);
  color: @text_primary;
}

.native-shell-badge-degraded {
  background: rgba(255, 184, 77, 0.16);
  border-color: rgba(255, 184, 77, 0.42);
  color: @text_primary;
}

.native-shell-badge-stopped {
  background: rgba(123, 196, 255, 0.14);
  border-color: rgba(123, 196, 255, 0.36);
  color: @text_primary;
}

.native-shell-metric-card {
  background: rgba(34, 39, 53, 0.82);
  border-radius: 14px;
  border: 1px solid rgba(58, 66, 86, 0.72);
  padding: 14px;
}

button {
  border-radius: 12px;
  padding: 10px 14px;
}

button.native-shell-button-primary {
  background-image: none;
  background-color: @accent_primary;
  border-color: @accent_primary;
  color: #0E1117;
}

button.native-shell-button-primary:hover {
  background-color: @accent_primary_hover;
}

button.native-shell-button-secondary {
  background-image: none;
  background-color: rgba(34, 39, 53, 0.96);
  border-color: rgba(58, 66, 86, 0.96);
  color: @text_primary;
}

button.native-shell-button-danger {
  background-image: none;
  background-color: rgba(255, 93, 115, 0.18);
  border-color: rgba(255, 93, 115, 0.52);
  color: @text_primary;
}

button.native-shell-button-secondary:disabled,
button.native-shell-button-primary:disabled,
button.native-shell-button-danger:disabled {
  opacity: 0.52;
}

textview {
  background: #0D1016;
  color: @text_primary;
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
    def __init__(
        self,
        gtk_module,
        gio_module,
        glib_module,
        gdk_module,
        tray_support: NativeShellTraySupport,
        runtime_service: SubvostAppService | None = None,
    ) -> None:
        self.Gtk = gtk_module
        self.Gio = gio_module
        self.GLib = glib_module
        self.Gdk = gdk_module
        self.tray_support = tray_support
        self.runtime_service = runtime_service or build_default_service(GUI_DIR, state=ServiceState())
        self.settings_paths = self.runtime_service.context.app_paths
        self.settings = NativeShellSettings.from_mapping(self.runtime_service.load_settings())
        self.log_path = self.settings_paths.store_dir / NATIVE_SHELL_LOG_FILENAME
        self.log_lines: list[str] = []
        self.app = self.Gtk.Application(application_id=NATIVE_SHELL_APP_ID, flags=self.Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.settings_window = None
        self.status_label = None
        self.log_buffer = None
        self.log_summary_label = None
        self.control_registration_id = None
        self.control_node_info = self.Gio.DBusNodeInfo.new_for_xml(CONTROL_INTROSPECTION_XML)
        self.tray_process: subprocess.Popen[str] | None = None
        self.allow_close = False
        self.did_initial_activation = False
        self.theme_dropdown = None
        self.settings_switches: dict[str, object] = {}
        self.dashboard_labels: dict[str, object] = {}
        self.dashboard_metrics: dict[str, object] = {}
        self.dashboard_action_buttons: dict[str, object] = {}
        self.dashboard_badge_box = None
        self.status_refresh_in_flight = False
        self.action_in_flight: str | None = None
        self.status_refresh_source_id = None
        self.last_status_payload: dict[str, Any] | None = None
        self.initial_gtk_dark_theme_preference: bool | None = None
        self.did_capture_initial_theme_preference = False

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
            self.start_status_polling()
            self.request_status_refresh(reason="initial-load")

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
        self.status_refresh_source_id = None
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
        subtitle_label = self.Gtk.Label(label="Desktop control shell for Subvost Xray TUN", xalign=0)
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
        add_css_class(panel, "native-shell-hero")

        title_label = self.Gtk.Label(label="Dashboard уже подключён к общему service-layer", xalign=0)
        add_css_class(title_label, "native-shell-page-title")
        description_label = self.Gtk.Label(
            label=(
                "GTK4 shell больше не живёт на stub-действиях: статус, ownership-guard и runtime-операции "
                "идут через тот же Python orchestration-layer, что и web GUI."
            ),
            xalign=0,
        )
        description_label.set_wrap(True)
        add_css_class(description_label, "native-shell-muted")

        self.status_label = self.Gtk.Label(xalign=0)
        self.status_label.set_wrap(True)
        add_css_class(self.status_label, "native-shell-status")
        self.set_status("Считываю текущее состояние bundle и подготавливаю Dashboard.")

        tray_note = self.Gtk.Label(
            label=f"Tray backend: {self.tray_support.reason}",
            xalign=0,
        )
        tray_note.set_wrap(True)
        add_css_class(tray_note, "native-shell-card-subtitle")
        self.dashboard_labels["tray_note"] = tray_note

        panel.append(title_label)
        panel.append(description_label)
        panel.append(self.status_label)
        panel.append(tray_note)
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
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=16)

        hero = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        add_css_class(hero, "native-shell-panel")
        add_css_class(hero, "native-shell-hero")
        hero_title = self.Gtk.Label(label="Runtime overview", xalign=0)
        add_css_class(hero_title, "native-shell-card-title")
        hero_state = self.Gtk.Label(label="Обновляю состояние…", xalign=0)
        add_css_class(hero_state, "native-shell-value-large")
        hero_detail = self.Gtk.Label(
            label="Service-layer собирает статус bundle, ownership и runtime-метрики.",
            xalign=0,
        )
        hero_detail.set_wrap(True)
        add_css_class(hero_detail, "native-shell-muted")
        hero_active = self.Gtk.Label(label="Активный узел: —", xalign=0)
        add_css_class(hero_active, "native-shell-card-subtitle")
        badge_box = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        hero.append(hero_title)
        hero.append(hero_state)
        hero.append(hero_detail)
        hero.append(hero_active)
        hero.append(badge_box)

        self.dashboard_labels["hero_state"] = hero_state
        self.dashboard_labels["hero_detail"] = hero_detail
        self.dashboard_labels["hero_active"] = hero_active
        self.dashboard_badge_box = badge_box

        split = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=16)
        split.append(self.build_dashboard_action_panel())
        split.append(self.build_dashboard_metrics_panel())

        container.append(hero)
        container.append(split)
        container.append(self.build_dashboard_details_panel())
        return container

    def build_dashboard_action_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_hexpand(True)
        add_css_class(panel, "native-shell-panel")
        title = self.Gtk.Label(label="Основные действия", xalign=0)
        add_css_class(title, "native-shell-card-title")
        subtitle = self.Gtk.Label(
            label="Root-запрос должен появляться только на runtime-действиях через `pkexec`.",
            xalign=0,
        )
        subtitle.set_wrap(True)
        add_css_class(subtitle, "native-shell-muted")

        action_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        button_styles = {
            "start-runtime": "native-shell-button-primary",
            "stop-runtime": "native-shell-button-danger",
            "capture-diagnostics": "native-shell-button-secondary",
        }
        for action_id in ("start-runtime", "stop-runtime", "capture-diagnostics"):
            button = self.Gtk.Button(label=tray_action_label(action_id))
            add_css_class(button, button_styles[action_id])
            button.connect("clicked", self.on_stub_button_clicked, action_id)
            self.dashboard_action_buttons[action_id] = button
            action_row.append(button)

        hint = self.Gtk.Label(
            label="Действия синхронизированы с тем же backend-контрактом, который обслуживает web GUI.",
            xalign=0,
        )
        hint.set_wrap(True)
        add_css_class(hint, "native-shell-card-subtitle")
        panel.append(title)
        panel.append(subtitle)
        panel.append(action_row)
        panel.append(hint)
        self.dashboard_labels["action_hint"] = hint
        return panel

    def build_dashboard_metrics_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_hexpand(True)
        add_css_class(panel, "native-shell-panel")
        title = self.Gtk.Label(label="Live metrics", xalign=0)
        add_css_class(title, "native-shell-card-title")
        grid = self.Gtk.Grid(column_spacing=12, row_spacing=12)

        metric_specs = (
            ("uptime", "Uptime"),
            ("rx", "RX"),
            ("tx", "TX"),
            ("tun", "TUN"),
            ("dns", "DNS"),
        )
        for index, (key, title_text) in enumerate(metric_specs):
            card = self.build_metric_card(title_text, key)
            grid.attach(card, index % 2, index // 2, 1, 1)

        panel.append(title)
        panel.append(grid)
        return panel

    def build_metric_card(self, title_text: str, key: str):
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        add_css_class(card, "native-shell-metric-card")
        title = self.Gtk.Label(label=title_text, xalign=0)
        add_css_class(title, "native-shell-card-subtitle")
        value = self.Gtk.Label(label="—", xalign=0)
        value.set_wrap(True)
        add_css_class(value, "native-shell-value")
        card.append(title)
        card.append(value)
        self.dashboard_metrics[key] = value
        return card

    def build_dashboard_details_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        add_css_class(panel, "native-shell-panel")
        title = self.Gtk.Label(label="Runtime context", xalign=0)
        add_css_class(title, "native-shell-card-title")
        grid = self.Gtk.Grid(column_spacing=12, row_spacing=12)

        detail_specs = (
            ("transport", "Transport / Security"),
            ("remote", "Remote endpoint / SNI"),
            ("routing", "Маршрутизация"),
            ("ownership", "Ownership"),
            ("last_action", "Последнее действие"),
            ("diagnostic", "Диагностика"),
            ("config", "Runtime config"),
            ("project_root", "Project root"),
        )
        for index, (key, title_text) in enumerate(detail_specs):
            card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
            add_css_class(card, "native-shell-metric-card")
            label = self.Gtk.Label(label=title_text, xalign=0)
            add_css_class(label, "native-shell-card-subtitle")
            value = self.Gtk.Label(label="—", xalign=0)
            value.set_wrap(True)
            add_css_class(value, "native-shell-value-muted")
            card.append(label)
            card.append(value)
            self.dashboard_labels[key] = value
            grid.attach(card, index % 2, index // 2, 1, 1)

        panel.append(title)
        panel.append(grid)
        return panel

    def build_subscriptions_page(self):
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(card, "native-shell-panel")
        card_title = self.Gtk.Label(label="Subscriptions и routing пойдут следующим этапом", xalign=0)
        add_css_class(card_title, "native-shell-card-title")
        body = self.Gtk.Label(
            label=(
                "Каркас страницы уже сохранён внутри общего native shell. "
                "Следующий этап добавит импорт URL-подписок, список узлов, ping, routing import и блок `GeoIP/Geosite`."
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
        summary = self.Gtk.Label(
            label="Здесь остаётся локальный журнал native shell и результаты runtime-действий этого окна.",
            xalign=0,
        )
        summary.set_wrap(True)
        add_css_class(summary, "native-shell-muted")
        self.log_summary_label = summary
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
        container.append(summary)
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
            label=(
                "Для GTK4 shell поддерживаются системный, светлый и тёмный режимы. "
                "Системный режим восстанавливает исходное GTK-предпочтение сессии."
            ),
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

        self.begin_runtime_action(action_id, source=source)

    def begin_runtime_action(self, action_id: str, *, source: str) -> None:
        if self.action_in_flight:
            current_label = tray_action_label(self.action_in_flight)
            self.set_status(f"Уже выполняется действие: {current_label}.")
            self.append_log(source, f"{tray_action_label(action_id)} пропущен: занято действием {current_label}.")
            return

        action_label = tray_action_label(action_id)
        self.action_in_flight = action_id
        self.set_status(f"{action_label}: выполняется через общий service-layer…")
        self.append_log(source, f"{action_label}: действие передано в общий runtime-service.")
        self.refresh_dashboard_controls()
        worker = threading.Thread(
            target=self.run_runtime_action_worker,
            args=(action_id, source),
            daemon=True,
        )
        worker.start()

    def run_runtime_action_worker(self, action_id: str, source: str) -> None:
        action_handlers = {
            "start-runtime": self.runtime_service.start_runtime,
            "stop-runtime": self.runtime_service.stop_runtime,
            "capture-diagnostics": self.runtime_service.capture_diagnostics,
        }
        handler = action_handlers.get(action_id)
        if handler is None:
            self.GLib.idle_add(self.finish_runtime_action, action_id, source, False, "Неизвестное действие.")
            return

        try:
            payload = handler()
        except Exception as exc:
            self.GLib.idle_add(self.finish_runtime_action, action_id, source, False, str(exc))
            return
        self.GLib.idle_add(self.finish_runtime_action, action_id, source, True, payload)

    def finish_runtime_action(self, action_id: str, source: str, ok: bool, payload: object) -> bool:
        action_label = tray_action_label(action_id)
        self.action_in_flight = None
        if ok:
            status_payload = payload if isinstance(payload, dict) else {}
            self.last_status_payload = status_payload
            self.update_dashboard_from_status(status_payload)
            message = str(status_payload.get("last_action", {}).get("message") or f"{action_label}: выполнено.")
            self.set_status(message)
            self.append_log(source, f"{action_label}: {message}")
        else:
            message = str(payload)
            self.set_status(f"{action_label}: {message}")
            self.append_log(source, f"{action_label}: ошибка: {message}")
            self.request_status_refresh(reason=f"{action_id}-error")
        self.refresh_dashboard_controls()
        return False

    def start_status_polling(self) -> None:
        if self.status_refresh_source_id is not None:
            return
        self.status_refresh_source_id = self.GLib.timeout_add_seconds(4, self.on_status_poll_timeout)

    def on_status_poll_timeout(self) -> bool:
        self.request_status_refresh(reason="poll", silent=True)
        return True

    def request_status_refresh(self, *, reason: str, silent: bool = False) -> None:
        if not hasattr(self, "runtime_service") or not hasattr(self, "GLib"):
            return
        if getattr(self, "status_refresh_in_flight", False) or getattr(self, "action_in_flight", None):
            return
        self.status_refresh_in_flight = True
        worker = threading.Thread(
            target=self.run_status_refresh_worker,
            args=(reason, silent),
            daemon=True,
        )
        worker.start()

    def run_status_refresh_worker(self, reason: str, silent: bool) -> None:
        try:
            payload = self.runtime_service.collect_status()
        except Exception as exc:
            self.GLib.idle_add(self.finish_status_refresh, reason, False, str(exc), silent)
            return
        self.GLib.idle_add(self.finish_status_refresh, reason, True, payload, silent)

    def finish_status_refresh(self, reason: str, ok: bool, payload: object, silent: bool) -> bool:
        self.status_refresh_in_flight = False
        if ok and isinstance(payload, dict):
            self.last_status_payload = payload
            self.update_dashboard_from_status(payload)
            if not silent and self.action_in_flight is None:
                self.set_status(self.status_message_from_payload(payload))
            return False

        if not silent:
            message = str(payload)
            self.set_status(f"Не удалось обновить статус bundle: {message}")
            self.append_log("status", f"Ошибка обновления Dashboard ({reason}): {message}")
        self.refresh_dashboard_controls()
        return False

    def status_message_from_payload(self, payload: dict[str, Any]) -> str:
        last_action = payload.get("last_action", {}) or {}
        if last_action.get("timestamp") and last_action.get("message"):
            return str(last_action["message"])
        return str(payload.get("summary", {}).get("description") or "Dashboard обновлён.")

    def update_dashboard_from_status(self, payload: dict[str, Any]) -> None:
        summary = payload.get("summary", {}) or {}
        runtime = payload.get("runtime", {}) or {}
        connection = payload.get("connection", {}) or {}
        routing = payload.get("routing", {}) or {}
        traffic = payload.get("traffic", {}) or {}
        artifacts = payload.get("artifacts", {}) or {}
        active_node = payload.get("active_node", {}) or {}
        last_action = payload.get("last_action", {}) or {}

        self.set_dashboard_label("hero_state", str(summary.get("label") or "—"))
        detail_parts = [str(summary.get("description") or "Статус bundle обновлён.")]
        blocking_reason = str(runtime.get("next_start_reason") or runtime.get("control_message") or "")
        if blocking_reason and summary.get("state") != "running":
            detail_parts.append(blocking_reason)
        self.set_dashboard_label("hero_detail", " ".join(part for part in detail_parts if part))

        active_name = str(active_node.get("name") or connection.get("active_name") or "—")
        protocol = str(connection.get("protocol_label") or "—")
        self.set_dashboard_label("hero_active", f"Активный узел: {active_name} · {protocol}")
        self.refresh_dashboard_badges(summary.get("badges", []), str(summary.get("state") or "stopped"))

        self.set_metric_value("uptime", self.format_connected_since(runtime.get("connected_since")))
        self.set_metric_value("rx", self.combine_rate_and_total(traffic.get("rx_rate_label"), traffic.get("rx_total_label")))
        self.set_metric_value("tx", self.combine_rate_and_total(traffic.get("tx_rate_label"), traffic.get("tx_total_label")))
        tun_line = str(summary.get("tun_line") or connection.get("tun_interface") or "—")
        self.set_metric_value("tun", tun_line)
        self.set_metric_value("dns", str(summary.get("dns_line") or connection.get("dns_servers") or "—"))

        transport = " · ".join(
            part for part in [connection.get("protocol_label"), connection.get("transport_label"), connection.get("security_label")] if part
        ) or "—"
        self.set_dashboard_label("transport", transport)
        remote_endpoint = str(connection.get("remote_endpoint") or "—")
        remote_sni = str(connection.get("remote_sni") or "—")
        self.set_dashboard_label("remote", f"{remote_endpoint}\nSNI: {remote_sni}")

        routing_label = "Маршрутизация выключена"
        if routing.get("enabled") and routing.get("runtime_ready"):
            routing_label = f"Включена: {routing.get('active_profile', {}).get('name') or runtime.get('routing_profile_name') or 'без имени'}"
        elif routing.get("enabled"):
            routing_label = f"Ошибка: {routing.get('runtime_error') or runtime.get('routing_error') or 'runtime не готов'}"
        elif runtime.get("routing_profile_name"):
            routing_label = f"Профиль выбран, но выключен: {runtime.get('routing_profile_name')}"
        self.set_dashboard_label("routing", routing_label)

        ownership = str(runtime.get("ownership_label") or "—")
        state_root = runtime.get("state_bundle_project_root")
        if state_root:
            ownership = f"{ownership}\n{state_root}"
        self.set_dashboard_label("ownership", ownership)

        last_action_message = str(last_action.get("message") or "Действий ещё не было.")
        if last_action.get("timestamp"):
            last_action_message = f"{last_action.get('timestamp')} · {last_action_message}"
        self.set_dashboard_label("last_action", last_action_message)

        latest_diagnostic = str(artifacts.get("latest_diagnostic") or "Диагностические дампы ещё не снимались.")
        self.set_dashboard_label("diagnostic", latest_diagnostic)
        config_value = f"{runtime.get('config_origin') or '—'}\n{runtime.get('active_xray_config') or '—'}"
        self.set_dashboard_label("config", config_value)
        self.set_dashboard_label("project_root", str(payload.get("project_root") or "—"))

        if self.log_summary_label is not None:
            logs_payload = payload.get("logs", {}) or {}
            latest_error = logs_payload.get("latest_error") or {}
            if latest_error:
                self.log_summary_label.set_label(f"Последняя ошибка: {latest_error.get('message')}")
            else:
                self.log_summary_label.set_label(last_action_message)

        self.refresh_dashboard_controls()

    def set_dashboard_label(self, key: str, value: str) -> None:
        label = getattr(self, "dashboard_labels", {}).get(key)
        if label is None:
            return
        label.set_label(value)

    def set_metric_value(self, key: str, value: str) -> None:
        label = getattr(self, "dashboard_metrics", {}).get(key)
        if label is None:
            return
        label.set_label(value)

    def combine_rate_and_total(self, rate_label: object, total_label: object) -> str:
        rate = str(rate_label or "—")
        total = str(total_label or "—")
        if rate == "—":
            return total
        return f"{rate}\nВсего: {total}"

    def format_connected_since(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "—"
        try:
            return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return raw

    def refresh_dashboard_badges(self, badges: object, summary_state: str) -> None:
        if self.dashboard_badge_box is None:
            return
        child = self.dashboard_badge_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.dashboard_badge_box.remove(child)
            child = next_child

        state_class = {
            "running": "native-shell-badge-running",
            "degraded": "native-shell-badge-degraded",
            "stopped": "native-shell-badge-stopped",
        }.get(summary_state, "native-shell-badge-stopped")
        for index, badge_text in enumerate(badges if isinstance(badges, list) else []):
            badge = self.Gtk.Label(label=str(badge_text), xalign=0)
            add_css_class(badge, "native-shell-badge")
            if index == 0:
                add_css_class(badge, state_class)
            self.dashboard_badge_box.append(badge)

    def refresh_dashboard_controls(self) -> None:
        runtime = (getattr(self, "last_status_payload", None) or {}).get("runtime", {}) or {}
        summary_state = (getattr(self, "last_status_payload", None) or {}).get("summary", {}).get("state")
        is_busy = getattr(self, "action_in_flight", None) is not None

        action_buttons = getattr(self, "dashboard_action_buttons", {})
        start_button = action_buttons.get("start-runtime")
        stop_button = action_buttons.get("stop-runtime")
        diag_button = action_buttons.get("capture-diagnostics")

        start_blocked = bool(runtime.get("start_blocked")) or summary_state == "running"
        if start_button is not None:
            start_button.set_sensitive(not is_busy and not start_blocked)
            start_button.set_tooltip_text(
                str(runtime.get("next_start_reason") or "Запустить runtime через общий service-layer.")
            )

        stop_allowed = bool(runtime.get("stop_allowed", True))
        if stop_button is not None:
            stop_button.set_sensitive(not is_busy and stop_allowed)
            stop_button.set_tooltip_text(
                str(runtime.get("control_message") or "Остановить текущий runtime и восстановить DNS.")
            )

        if diag_button is not None:
            diag_button.set_sensitive(not is_busy)
            diag_button.set_tooltip_text("Снять диагностический дамп bundle.")

        if is_busy:
            self.set_dashboard_label("action_hint", f"Выполняется: {tray_action_label(self.action_in_flight or '')}.")
            return

        if runtime.get("start_blocked"):
            self.set_dashboard_label("action_hint", str(runtime.get("next_start_reason") or "Старт сейчас заблокирован."))
            return
        if runtime.get("routing_enabled") and not runtime.get("routing_ready"):
            self.set_dashboard_label("action_hint", str(runtime.get("routing_error") or "Routing runtime пока не готов."))
            return
        self.set_dashboard_label(
            "action_hint",
            "Root-запрос должен появляться только на `Старт`, `Стоп` и `Диагностика`.",
        )

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
        else:
            self.set_status(f"Настройки shell сохранены. Tray fallback: {self.tray_support.reason}")
        self.request_status_refresh(reason="settings-change", silent=True)

    def persist_settings(self) -> None:
        self.runtime_service.save_settings(
            self.settings.file_logs_enabled,
            close_to_tray=self.settings.close_to_tray,
            start_minimized_to_tray=self.settings.start_minimized_to_tray,
            theme=self.settings.theme,
        )

    def capture_initial_theme_preference(self, settings) -> None:
        if self.did_capture_initial_theme_preference:
            return
        self.did_capture_initial_theme_preference = True
        get_property = getattr(settings, "get_property", None)
        if get_property is None:
            return
        try:
            self.initial_gtk_dark_theme_preference = bool(get_property("gtk-application-prefer-dark-theme"))
        except (TypeError, ValueError):
            self.initial_gtk_dark_theme_preference = None

    def apply_theme_preference(self, theme: str) -> None:
        settings = self.Gtk.Settings.get_default()
        if settings is None:
            return
        self.capture_initial_theme_preference(settings)
        try:
            if theme == "dark":
                value = True
            elif theme == "light":
                value = False
            elif self.initial_gtk_dark_theme_preference is not None:
                value = self.initial_gtk_dark_theme_preference
            else:
                return
            settings.set_property("gtk-application-prefer-dark-theme", value)
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
        self.handle_tray_helper_failure(return_code, stage="startup")
        return False

    def poll_tray_helper(self) -> bool:
        if self.tray_process is None:
            return False
        return_code = self.tray_process.poll()
        if return_code is None:
            return True
        self.handle_tray_helper_failure(return_code, stage="runtime")
        return False

    def handle_tray_helper_failure(self, return_code: int, *, stage: str) -> None:
        self.tray_support = build_tray_support(
            watcher_name=None,
            indicator_candidate=None,
            error=f"Tray helper {('завершился' if stage == 'startup' else 'остановился')} с кодом {return_code}.",
        )
        self.tray_process = None
        self.append_log("tray", self.tray_support.reason)
        self.set_dashboard_label("tray_note", f"Tray backend: {self.tray_support.reason}")
        if self.window is not None and not self.window.get_visible():
            self.window.present()
            self.set_status(
                "Tray backend недоступен. Главное окно автоматически показано, чтобы приложение не осталось скрытым."
            )
            self.append_log("tray", "Главное окно автоматически показано после деградации tray backend.")
            self.request_status_refresh(reason="tray-degraded", silent=True)
            return
        self.refresh_status_after_settings_change()

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
