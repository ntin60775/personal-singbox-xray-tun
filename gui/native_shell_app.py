#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import re
import subprocess
import sys
import threading
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from embedded_webview import ensure_graphical_session
from native_shell_shared import (
    NATIVE_SHELL_APP_ID,
    NATIVE_SHELL_APPINDICATOR_CANDIDATES,
    NATIVE_SHELL_CONTROL_INTERFACE,
    NATIVE_SHELL_CONTROL_OBJECT_PATH,
    NATIVE_SHELL_LOG_FILTER_VALUES,
    NATIVE_SHELL_PAGES,
    NATIVE_SHELL_TITLE,
    NATIVE_SHELL_TRAY_ACTIONS,
    NATIVE_SHELL_TRAY_WATCHER_CANDIDATES,
    NativeShellSettings,
    NativeShellTraySupport,
    active_node_from_store_snapshot,
    active_profile_from_store_snapshot,
    active_routing_profile_from_store_snapshot,
    build_native_shell_log_text,
    build_startup_notes,
    build_tray_support,
    filter_log_entries,
    log_entries_from_status,
    latest_error_from_log_entries,
    native_shell_theme_label,
    native_shell_action_label,
    native_shell_log_filter_label,
    native_shell_log_level_label,
    native_shell_log_source_label,
    normalize_native_shell_log_filter,
    normalize_native_shell_theme,
    ping_snapshot_from_status,
    resolve_selected_subscription_id,
    routing_from_store_snapshot,
    routing_profiles_from_store_snapshot,
    selected_profile_from_store_snapshot,
    selected_subscription_from_store_snapshot,
    subscriptions_from_store_snapshot,
    should_hide_on_close,
    should_start_hidden,
)
from subvost_app_service import ServiceState, SubvostAppService, build_default_service, log_level_from_text


GUI_DIR = Path(__file__).resolve().parent
ASSETS_DIR = GUI_DIR.parent / "assets"
ICON_ASSET_PATH = ASSETS_DIR / "subvost-xray-tun-icon.svg"
APP_ICON_NAME = "subvost-xray-tun-icon"
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
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 960
DASHBOARD_NODE_CARD_COLUMNS = 4
DASHBOARD_NODE_CARD_SPACING = 12
DASHBOARD_NODE_CARD_WIDTH = (
    DEFAULT_WINDOW_WIDTH
    - (14 * 2)  # root padding
    - (4 * 2)   # page margin
    - (14 * 2)  # dashboard panel padding
    - 48        # scroller gutter and layout breathing room
    - (DASHBOARD_NODE_CARD_SPACING * (DASHBOARD_NODE_CARD_COLUMNS - 1))
) // DASHBOARD_NODE_CARD_COLUMNS
DASHBOARD_NODE_CARD_HEIGHT = 132
NODE_FLAG_PREFIX_RE = re.compile(r"^(?:[\U0001F1E6-\U0001F1FF]{2})\s*")
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

headerbar {
  min-height: 36px;
  padding: 0 8px;
  background: rgba(21, 24, 33, 0.98);
  box-shadow: inset 0 -1px rgba(58, 66, 86, 0.72);
}

stackswitcher button {
  min-height: 28px;
  padding: 4px 12px;
  border-radius: 999px;
  background-image: none;
  background-color: rgba(34, 39, 53, 0.72);
  border-color: rgba(58, 66, 86, 0.82);
  color: @text_secondary;
}

stackswitcher button:checked {
  background-color: rgba(255, 99, 99, 0.18);
  border-color: rgba(255, 99, 99, 0.44);
  color: @text_primary;
}

.native-shell-root {
  color: @text_primary;
  padding: 14px;
  background:
    radial-gradient(circle at top left, rgba(255, 99, 99, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(21, 24, 33, 0.96), rgba(16, 18, 24, 0.98));
}

.native-shell-panel {
  background: rgba(27, 31, 42, 0.92);
  border-radius: 14px;
  border: 1px solid rgba(58, 66, 86, 0.72);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
  padding: 14px;
}

.native-shell-muted {
  color: @text_muted;
}

.native-shell-window-title {
  color: @text_primary;
  font-size: 14px;
  font-weight: 700;
}

.native-shell-status {
  color: @text_secondary;
  font-weight: 600;
}

.native-shell-page-title {
  color: @text_primary;
  font-size: 18px;
  font-weight: 700;
}

.native-shell-card-title {
  color: @text_primary;
  font-size: 15px;
  font-weight: 700;
}

.native-shell-card-subtitle {
  color: @text_secondary;
  font-size: 12px;
}

.native-shell-hero {
  background:
    linear-gradient(180deg, rgba(34, 39, 53, 0.96), rgba(27, 31, 42, 0.92)),
    radial-gradient(circle at top right, rgba(255, 99, 99, 0.16), transparent 38%);
}

.native-shell-statusbar {
  padding: 12px 14px;
}

.native-shell-statusline {
  color: @text_primary;
  font-size: 16px;
  font-weight: 700;
}

.native-shell-statusline-meta {
  color: @text_secondary;
  font-size: 13px;
}

.native-shell-connection-row {
  min-height: 38px;
}

.native-shell-status-pill {
  background: rgba(34, 39, 53, 0.82);
  border-radius: 999px;
  border: 1px solid rgba(58, 66, 86, 0.68);
  padding: 7px 12px;
}

.native-shell-status-pill-traffic {
  min-width: 360px;
}

.native-shell-status-dot {
  font-size: 18px;
  font-weight: 700;
}

.native-shell-status-dot-running {
  color: @state_success;
}

.native-shell-status-dot-warning {
  color: @state_warning;
}

.native-shell-status-dot-stopped {
  color: @state_info;
}

.native-shell-status-feedback {
  color: @text_secondary;
  font-size: 12px;
}

.native-shell-value {
  color: @text_primary;
  font-size: 18px;
  font-weight: 700;
}

.native-shell-value-large {
  color: @text_primary;
  font-size: 20px;
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

.native-shell-status-badge-label {
  color: @text_primary;
  font-size: 12px;
}

.native-shell-status-badge-icon {
  color: @text_primary;
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
  padding: 10px;
}

button {
  border-radius: 10px;
  min-height: 38px;
  padding: 8px 12px;
  transition: background-color 140ms ease-out, border-color 140ms ease-out, box-shadow 140ms ease-out, color 140ms ease-out;
}

button.native-shell-button-primary {
  background-image: none;
  background-color: @accent_primary;
  border-color: @accent_primary;
  color: #0E1117;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(255, 116, 116, 0.2);
}

button.native-shell-button-primary:hover {
  background-color: @accent_primary_hover;
  border-color: @accent_primary_hover;
  box-shadow: inset 0 0 0 1px rgba(255, 116, 116, 0.34), 0 0 0 2px rgba(255, 99, 99, 0.14);
}

button.native-shell-button-primary:active {
  background-color: rgba(255, 116, 116, 0.78);
  border-color: rgba(255, 116, 116, 0.96);
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.34);
}

button.native-shell-button-primary:focus {
  box-shadow: inset 0 0 0 1px rgba(255, 116, 116, 0.32), 0 0 0 2px rgba(255, 99, 99, 0.24);
}

button.native-shell-button-secondary {
  background-image: none;
  background-color: rgba(34, 39, 53, 0.96);
  border-color: rgba(58, 66, 86, 0.96);
  color: @text_primary;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(91, 102, 126, 0.42);
}

button.native-shell-button-secondary:hover {
  background-color: rgba(47, 54, 72, 0.98);
  border-color: rgba(123, 196, 255, 0.42);
  color: @text_primary;
  box-shadow: inset 0 0 0 1px rgba(123, 196, 255, 0.18), 0 0 0 2px rgba(123, 196, 255, 0.08);
}

button.native-shell-button-secondary:active {
  background-color: rgba(23, 27, 37, 0.98);
  border-color: rgba(123, 196, 255, 0.58);
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.34);
}

button.native-shell-button-secondary:focus {
  border-color: rgba(123, 196, 255, 0.48);
  box-shadow: inset 0 0 0 1px rgba(123, 196, 255, 0.22), 0 0 0 2px rgba(123, 196, 255, 0.16);
}

button.native-shell-button-danger {
  background-image: none;
  background-color: rgba(255, 93, 115, 0.18);
  border-color: rgba(255, 93, 115, 0.52);
  color: @text_primary;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(255, 93, 115, 0.16);
}

button.native-shell-button-danger:hover {
  background-color: rgba(255, 93, 115, 0.26);
  border-color: rgba(255, 93, 115, 0.72);
  box-shadow: inset 0 0 0 1px rgba(255, 93, 115, 0.24), 0 0 0 2px rgba(255, 93, 115, 0.10);
}

button.native-shell-button-danger:active {
  background-color: rgba(255, 93, 115, 0.14);
  border-color: rgba(255, 93, 115, 0.82);
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.34);
}

button.native-shell-button-secondary:disabled,
button.native-shell-button-primary:disabled,
button.native-shell-button-danger:disabled {
  opacity: 0.52;
  box-shadow: none;
}

.native-shell-action-feedback {
  background: rgba(34, 39, 53, 0.82);
  border-radius: 10px;
  border: 1px solid rgba(58, 66, 86, 0.82);
  color: @text_secondary;
  font-size: 12px;
  padding: 8px 10px;
}

.native-shell-action-feedback-busy {
  border-color: rgba(255, 184, 77, 0.42);
  color: @state_warning;
}

.native-shell-action-feedback-success {
  border-color: rgba(61, 220, 151, 0.42);
  color: @state_success;
}

.native-shell-action-feedback-error {
  border-color: rgba(255, 93, 115, 0.48);
  color: @state_danger;
}

entry.native-shell-entry,
textview.native-shell-input {
  background: rgba(13, 16, 22, 0.96);
  color: @text_primary;
  border-radius: 12px;
  border: 1px solid rgba(58, 66, 86, 0.96);
}

.native-shell-inline-actions {
  border-spacing: 8px 0;
}

button.native-shell-nav-button,
button.native-shell-icon-button {
  background-image: none;
  background-color: rgba(34, 39, 53, 0.72);
  border-color: rgba(58, 66, 86, 0.82);
  color: @text_primary;
}

button.native-shell-nav-button {
  padding: 10px 14px;
}

button.native-shell-nav-button-active {
  background-color: rgba(255, 99, 99, 0.18);
  border-color: rgba(255, 99, 99, 0.44);
}

button.native-shell-icon-button {
  min-width: 0;
  padding: 6px 8px;
}

.native-shell-page-scroll,
.native-shell-log-scroller {
  background: transparent;
}

.native-shell-conflict-bar {
  background: rgba(255, 184, 77, 0.12);
  border-radius: 12px;
  border: 1px solid rgba(255, 184, 77, 0.42);
}

.native-shell-subscriptions-root,
.native-shell-subscriptions-right {
  min-height: 0;
}

.native-shell-node-grid {
  min-height: 0;
}

.native-shell-node-grid-row {
  min-height: 0;
}

.native-shell-node-card {
  background: rgba(34, 39, 53, 0.58);
  border-radius: 14px;
  border: 1px solid rgba(58, 66, 86, 0.6);
  padding: 12px;
}

.native-shell-node-card-clickable:hover {
  background: rgba(42, 48, 64, 0.72);
  border-color: rgba(123, 196, 255, 0.32);
}

.native-shell-node-card-active {
  background: rgba(123, 196, 255, 0.12);
  border-color: rgba(123, 196, 255, 0.46);
  box-shadow: inset 0 0 0 1px rgba(123, 196, 255, 0.18);
}

.native-shell-node-card-disabled {
  opacity: 0.72;
}

.native-shell-node-empty {
  padding: 8px 4px 2px 4px;
}

.native-shell-sidebar {
  background: rgba(13, 16, 22, 0.74);
  border-radius: 14px;
  border: 1px solid rgba(58, 66, 86, 0.7);
  padding: 8px;
}

.native-shell-listbox {
  background: transparent;
}

.native-shell-list-row {
  background: rgba(34, 39, 53, 0.58);
  border-radius: 14px;
  border: 1px solid rgba(58, 66, 86, 0.6);
  padding: 10px;
}

.native-shell-list-row:selected {
  background: rgba(255, 99, 99, 0.16);
  border-color: rgba(255, 99, 99, 0.42);
}

.native-shell-row-title {
  color: @text_primary;
  font-size: 14px;
  font-weight: 700;
}

.native-shell-row-meta {
  color: @text_secondary;
  font-size: 11px;
}

.native-shell-row-copy {
  color: @text_muted;
  font-size: 11px;
}

.native-shell-chip-success {
  background: rgba(61, 220, 151, 0.16);
  border-color: rgba(61, 220, 151, 0.42);
}

.native-shell-chip-warning {
  background: rgba(255, 184, 77, 0.16);
  border-color: rgba(255, 184, 77, 0.4);
}

.native-shell-chip-danger {
  background: rgba(255, 93, 115, 0.18);
  border-color: rgba(255, 93, 115, 0.46);
}

.native-shell-chip-accent {
  background: rgba(123, 196, 255, 0.16);
  border-color: rgba(123, 196, 255, 0.44);
}

textview {
  background: #0D1016;
  color: @text_primary;
}

textview.native-shell-log-view,
textview.native-shell-log-view text {
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
        return build_tray_support(watcher_name=None, indicator_candidate=None, error="Трей отключён аргументом запуска.")

    try:
        versions = available_namespace_versions(("Gtk",) + tuple(candidate[0] for candidate in NATIVE_SHELL_APPINDICATOR_CANDIDATES))
    except Exception as exc:
        return build_tray_support(watcher_name=None, indicator_candidate=None, error=f"Не удалось прочитать GI-окружение: {exc}")

    if "3.0" not in versions.get("Gtk", set()):
        return build_tray_support(
            watcher_name=None,
            indicator_candidate=None,
            error="Не найден Gtk 3.0 для трей-хелпера.",
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


def remove_css_class(widget, css_class: str) -> None:
    if hasattr(widget, "remove_css_class"):
        widget.remove_css_class(css_class)


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
        self.shell_log_entries: list[dict[str, Any]] = []
        self.app = self.Gtk.Application(application_id=NATIVE_SHELL_APP_ID, flags=self.Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.settings_window = None
        self.settings_update_button = None
        self.settings_update_feedback_label = None
        self.stack = None
        self.stack_switcher = None
        self.status_label = None
        self.log_buffer = None
        self.log_summary_label = None
        self.log_meta_label = None
        self.log_export_label = None
        self.log_copy_button = None
        self.log_export_button = None
        self.log_filter = "all"
        self.log_filter_buttons: dict[str, object] = {}
        self.last_log_export_path: Path | None = None
        self.control_registration_id = None
        self.control_node_info = self.Gio.DBusNodeInfo.new_for_xml(CONTROL_INTROSPECTION_XML)
        self.tray_process: subprocess.Popen[str] | None = None
        self.allow_close = False
        self.did_initial_activation = False
        self.settings_switches: dict[str, object] = {}
        self.dashboard_labels: dict[str, object] = {}
        self.dashboard_metrics: dict[str, object] = {}
        self.dashboard_action_buttons: dict[str, object] = {}
        self.dashboard_primary_action_id: str | None = None
        self.dashboard_badge_box = None
        self.dashboard_status_meta_box = None
        self.dashboard_conflict_bar = None
        self.dashboard_conflict_label = None
        self.dashboard_takeover_button = None
        self.diagnostic_takeover_button = None
        self.diagnostic_action_label = None
        self.dashboard_dns_button = None
        self.dashboard_dns_compact_text = "—"
        self.dashboard_dns_full_text = "—"
        self.dashboard_dns_server_count = 0
        self.dashboard_dns_expanded = False
        self.dashboard_tun_line = "—"
        self.diagnostic_labels: dict[str, object] = {}
        self.last_store_payload: dict[str, Any] | None = None
        self.selected_subscription_id: str | None = None
        self.subscription_url_entry = None
        self.subscription_list_box = None
        self.node_list_box = None
        self.dashboard_node_grid_box = None
        self.dashboard_node_grid_scroller = None
        self.dashboard_node_empty_label = None
        self.routing_profile_list_box = None
        self.routing_import_buffer = None
        self.subscription_labels: dict[str, object] = {}
        self.subscription_action_buttons: dict[str, object] = {}
        self.routing_action_buttons: dict[str, object] = {}
        self.subscription_row_click_suppressed = False
        self.node_row_click_suppressed = False
        self.status_refresh_in_flight = False
        self.action_in_flight: str | None = None
        self.status_refresh_source_id = None
        self.dashboard_uptime_source_id = None
        self.last_status_payload: dict[str, Any] | None = None

        self.app.connect("activate", self.on_activate)
        self.app.connect("shutdown", self.on_shutdown)
        self.app.connect("startup", self.on_startup)

    def on_startup(self, app) -> None:
        self.apply_theme_preference(self.settings.theme)
        self.append_log("native-shell", "Нативная GTK4-оболочка запускается без раннего запроса прав.")
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
            self.start_dashboard_uptime_timer()
            self.request_status_refresh(reason="initial-load")

        if not self.did_initial_activation and should_start_hidden(self.settings, self.tray_support):
            self.window.set_visible(False)
            self.did_initial_activation = True
            self.set_status("Приложение запущено в свёрнутом режиме в трее.")
            self.append_log("tray", "Главное окно стартовало скрытым по настройке запуска в трей.")
            return

        self.did_initial_activation = True
        self.show_window(reason="activate")

    def on_shutdown(self, app) -> None:
        self.stop_tray_helper()
        self.status_refresh_source_id = None
        self.dashboard_uptime_source_id = None
        connection = app.get_dbus_connection()
        if connection is not None and self.control_registration_id is not None:
            connection.unregister_object(self.control_registration_id)
            self.control_registration_id = None

    def register_control_interface(self) -> None:
        if self.control_registration_id is not None:
            return
        connection = self.app.get_dbus_connection()
        if connection is None:
            self.append_log("dbus", "Не удалось получить D-Bus-подключение для управляющего интерфейса.")
            return
        interface_info = self.control_node_info.interfaces[0]
        self.control_registration_id = connection.register_object(
            NATIVE_SHELL_CONTROL_OBJECT_PATH,
            interface_info,
            self.on_control_method_call,
            self.on_control_get_property,
            None,
        )
        self.append_log("dbus", f"Управляющий интерфейс опубликован по пути {NATIVE_SHELL_CONTROL_OBJECT_PATH}.")

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
        window.set_size_request(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        window.set_resizable(False)
        if hasattr(window, "set_icon_name"):
            window.set_icon_name(APP_ICON_NAME)
        window.connect("close-request", self.on_close_request)

        display = self.Gdk.Display.get_default()
        provider = self.Gtk.CssProvider()
        provider.load_from_data(GTK4_WINDOW_CSS)
        self.Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        root.set_vexpand(True)
        add_css_class(root, "native-shell-root")
        stack = self.build_stack()
        header = self.build_header_bar(stack)
        root.append(stack)
        window.set_titlebar(header)
        window.set_child(root)
        return window

    def build_header_bar(self, stack):
        header = self.Gtk.HeaderBar()
        header.set_show_title_buttons(True)

        title_label = self.Gtk.Label(label=NATIVE_SHELL_TITLE, xalign=0)
        add_css_class(title_label, "native-shell-window-title")
        header.pack_start(title_label)

        switcher = self.Gtk.StackSwitcher()
        switcher.set_stack(stack)
        self.stack_switcher = switcher
        header.set_title_widget(switcher)

        settings_button = self.Gtk.Button(label="Настройки")
        add_css_class(settings_button, "native-shell-button-secondary")
        settings_button.connect("clicked", lambda *_args: self.open_settings_window())
        header.pack_end(settings_button)
        return header

    def build_stack(self):
        stack = self.Gtk.Stack()
        stack.set_hexpand(True)
        stack.set_vexpand(True)
        stack.set_transition_type(self.Gtk.StackTransitionType.CROSSFADE)
        self.stack = stack

        for page in NATIVE_SHELL_PAGES:
            stack.add_titled(self.build_page(page), page.page_id, page.title)
        stack.set_visible_child_name("dashboard")
        return stack

    def build_page(self, page):
        page_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        page_box.set_margin_top(4)
        page_box.set_margin_bottom(4)
        page_box.set_margin_start(4)
        page_box.set_margin_end(4)
        if page.page_id == "dashboard":
            page_box.append(self.build_dashboard_page())
        elif page.page_id == "subscriptions":
            page_box.append(self.build_subscriptions_page())
        elif page.page_id == "log":
            page_box.append(self.build_log_page())

        scrolled = self.Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        add_css_class(scrolled, "native-shell-page-scroll")
        scrolled.set_child(page_box)
        return scrolled

    def build_named_panel(self, title_text: str, *, subtitle: str | None = None):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(panel, "native-shell-panel")
        title = self.Gtk.Label(label=title_text, xalign=0)
        add_css_class(title, "native-shell-card-title")
        panel.append(title)
        if subtitle:
            subtitle_label = self.Gtk.Label(label=subtitle, xalign=0)
            subtitle_label.set_wrap(True)
            add_css_class(subtitle_label, "native-shell-muted")
            panel.append(subtitle_label)
        body = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        panel.append(body)
        return panel, body

    def build_dashboard_status_row(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=4)
        container.set_hexpand(True)

        row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_hexpand(True)
        add_css_class(row, "native-shell-connection-row")

        icon_label = self.Gtk.Label(label="●", xalign=0)
        add_css_class(icon_label, "native-shell-status-dot")
        add_css_class(icon_label, "native-shell-status-dot-stopped")
        self.dashboard_labels["hero_state_icon"] = icon_label

        title_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)

        state_label = self.Gtk.Label(label="Состояние обновляется…", xalign=0)
        state_label.set_wrap(True)
        add_css_class(state_label, "native-shell-statusline")
        self.dashboard_labels["hero_state"] = state_label

        node_label = self.Gtk.Label(label="", xalign=0)
        node_label.set_hexpand(True)
        node_label.set_wrap(True)
        add_css_class(node_label, "native-shell-statusline-meta")
        self.dashboard_labels["hero_active"] = node_label

        title_box.append(state_label)
        title_box.append(node_label)

        meta_box = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        self.dashboard_status_meta_box = meta_box

        uptime_label = self.Gtk.Label(label="", xalign=0)
        add_css_class(uptime_label, "native-shell-status-pill")
        uptime_label.set_visible(False)
        self.dashboard_labels["hero_uptime"] = uptime_label

        traffic_label = self.Gtk.Label(label="Принято: —  Отправлено: —", xalign=0)
        if hasattr(traffic_label, "set_use_markup"):
            traffic_label.set_use_markup(True)
        traffic_label.set_wrap(True)
        add_css_class(traffic_label, "native-shell-status-pill")
        add_css_class(traffic_label, "native-shell-status-pill-traffic")
        traffic_label.set_visible(False)
        self.dashboard_labels["hero_traffic"] = traffic_label

        meta_box.append(uptime_label)
        meta_box.append(traffic_label)

        subscription_label = self.Gtk.Label(label="", xalign=0)
        subscription_label.set_wrap(True)
        subscription_label.set_margin_start(28)
        add_css_class(subscription_label, "native-shell-muted")
        self.dashboard_labels["hero_subscription"] = subscription_label

        row.append(icon_label)
        row.append(title_box)
        row.append(meta_box)
        container.append(row)
        container.append(subscription_label)
        return container

    def build_dashboard_page(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        container.set_vexpand(True)
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_vexpand(True)
        add_css_class(panel, "native-shell-panel")

        primary_button = self.Gtk.Button(label="Подключиться")
        add_css_class(primary_button, "native-shell-button-primary")
        primary_button.set_tooltip_text("Запустить подключение через выбранный узел.")
        primary_button.connect("clicked", self.on_dashboard_primary_action_clicked)
        self.dashboard_action_buttons["primary-connect"] = primary_button

        diagnostics_button = self.Gtk.Button(label="Диагностика")
        add_css_class(diagnostics_button, "native-shell-button-secondary")
        diagnostics_button.set_tooltip_text("Открыть диагностику подключения и служебные файлы.")
        diagnostics_button.connect("clicked", lambda *_args: self.show_page("log"))
        self.dashboard_action_buttons["open-diagnostics"] = diagnostics_button

        action_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        action_row.set_hexpand(True)
        action_row.set_homogeneous(True)
        primary_button.set_hexpand(True)
        diagnostics_button.set_hexpand(True)
        action_row.append(primary_button)
        action_row.append(diagnostics_button)

        self.status_label = self.Gtk.Label(xalign=0)
        self.status_label.set_wrap(True)
        add_css_class(self.status_label, "native-shell-status-feedback")
        self.set_status("Считываю текущее состояние подключения.")

        info_bar = self.Gtk.InfoBar()
        info_bar.set_message_type(self.Gtk.MessageType.WARNING)
        info_bar.set_visible(False)
        info_bar.set_revealed(False)
        add_css_class(info_bar, "native-shell-conflict-bar")
        info_label = self.Gtk.Label(label="—", xalign=0)
        info_label.set_wrap(True)
        info_bar.add_child(info_label)
        takeover_button = self.Gtk.Button(label="Перехватить")
        add_css_class(takeover_button, "native-shell-button-secondary")
        takeover_button.set_tooltip_text("Остановить активное подключение другой установки и освободить текущее окно.")
        takeover_button.connect("clicked", self.on_takeover_requested)
        info_bar.add_action_widget(takeover_button, self.Gtk.ResponseType.ACCEPT)
        self.dashboard_conflict_bar = info_bar
        self.dashboard_conflict_label = info_label
        self.dashboard_takeover_button = takeover_button

        states_head = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        states_head.set_hexpand(True)
        states_title = self.Gtk.Label(label="Статусы", xalign=0)
        add_css_class(states_title, "native-shell-card-subtitle")
        badges_box = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        badges_box.set_hexpand(True)
        self.dashboard_badge_box = badges_box
        states_head.append(states_title)
        states_head.append(badges_box)

        panel.append(self.build_dashboard_status_row())
        panel.append(action_row)
        panel.append(info_bar)
        panel.append(self.status_label)
        panel.append(states_head)
        panel.append(self.build_nodes_panel())
        container.append(panel)
        return container

    def build_diagnostics_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)

        state_panel, state_body = self.build_named_panel(
            "Состояние",
            subtitle="Конфликт экземпляров и текущее управляющее состояние подключения.",
        )
        state_label = self.Gtk.Label(label="—", xalign=0)
        state_label.set_wrap(True)
        add_css_class(state_label, "native-shell-value-muted")
        state_body.append(state_label)
        state_actions = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        takeover_button = self.Gtk.Button(label="Перехватить")
        add_css_class(takeover_button, "native-shell-button-secondary")
        takeover_button.set_tooltip_text("Остановить активное подключение другой установки и освободить текущее окно.")
        takeover_button.connect("clicked", self.on_takeover_requested)
        self.diagnostic_takeover_button = takeover_button
        state_actions.append(takeover_button)
        state_body.append(state_actions)
        self.diagnostic_labels["diagnostic_status"] = state_label

        connection_panel, connection_body = self.build_named_panel(
            "Параметры подключения",
            subtitle="Протокол, адрес, SNI и состояние маршрутизации.",
        )
        connection_label = self.Gtk.Label(label="—", xalign=0)
        connection_label.set_wrap(True)
        add_css_class(connection_label, "native-shell-value-muted")
        connection_body.append(connection_label)
        self.diagnostic_labels["diagnostic_connection"] = connection_label

        files_panel, files_body = self.build_named_panel(
            "Файлы и дампы",
            subtitle="Рабочие пути и диагностический дамп текущего окна.",
        )
        files_label = self.Gtk.Label(label="—", xalign=0)
        files_label.set_wrap(True)
        add_css_class(files_label, "native-shell-value-muted")
        files_body.append(files_label)
        files_actions = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        capture_button = self.Gtk.Button(label="Снять дамп")
        add_css_class(capture_button, "native-shell-button-secondary")
        capture_button.connect("clicked", self.on_stub_button_clicked, "capture-diagnostics")
        self.dashboard_action_buttons["capture-diagnostics"] = capture_button
        cleanup_button = self.Gtk.Button(label="Очистить служебные файлы")
        add_css_class(cleanup_button, "native-shell-button-secondary")
        cleanup_button.set_tooltip_text("Удалить только безопасно очищаемые state, DNS backup и старые диагностические файлы.")
        cleanup_button.connect("clicked", self.on_cleanup_artifacts_clicked)
        self.dashboard_action_buttons["cleanup-artifacts"] = cleanup_button
        files_actions.append(capture_button)
        files_actions.append(cleanup_button)
        files_body.append(files_actions)
        action_feedback_label = self.Gtk.Label(label="Готово к диагностическим действиям.", xalign=0)
        action_feedback_label.set_wrap(True)
        add_css_class(action_feedback_label, "native-shell-action-feedback")
        files_body.append(action_feedback_label)
        self.diagnostic_action_label = action_feedback_label
        self.diagnostic_labels["diagnostic_files"] = files_label

        instance_panel, instance_body = self.build_named_panel(
            "Экземпляры",
            subtitle="Где сейчас работает активный runtime и какой проект открыт в этом окне.",
        )
        instance_label = self.Gtk.Label(label="—", xalign=0)
        instance_label.set_wrap(True)
        add_css_class(instance_label, "native-shell-value-muted")
        instance_body.append(instance_label)
        self.diagnostic_labels["diagnostic_instance"] = instance_label

        last_action_panel, last_action_body = self.build_named_panel(
            "Последнее действие",
            subtitle="Итог последней команды и её временная отметка.",
        )
        last_action_label = self.Gtk.Label(label="—", xalign=0)
        last_action_label.set_wrap(True)
        add_css_class(last_action_label, "native-shell-value-muted")
        last_action_body.append(last_action_label)
        self.diagnostic_labels["diagnostic_last_action"] = last_action_label

        panel.append(state_panel)
        panel.append(connection_panel)
        panel.append(files_panel)
        panel.append(instance_panel)
        panel.append(last_action_panel)
        return panel

    def build_subscriptions_page(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)

        action_panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        add_css_class(action_panel, "native-shell-panel")
        title = self.Gtk.Label(label="Подписки", xalign=0)
        add_css_class(title, "native-shell-card-title")
        summary = self.Gtk.Label(
            label="Подписки управляются здесь, а карточки узлов выбранного источника показываются на вкладке `Подключение`; справа остаётся маршрутизация.",
            xalign=0,
        )
        summary.set_wrap(True)
        add_css_class(summary, "native-shell-muted")
        self.subscription_labels["summary"] = summary

        input_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        input_row.set_hexpand(True)
        entry = self.Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_placeholder_text("https://example.com/subscription")
        add_css_class(entry, "native-shell-entry")
        entry.connect("activate", lambda *_args: self.on_add_subscription_requested())
        self.subscription_url_entry = entry

        add_button = self.Gtk.Button(label="Добавить")
        add_css_class(add_button, "native-shell-button-primary")
        add_button.connect("clicked", lambda *_args: self.on_add_subscription_requested())
        self.subscription_action_buttons["subscriptions-add"] = add_button

        refresh_all_button = self.Gtk.Button(label="Обновить все")
        add_css_class(refresh_all_button, "native-shell-button-secondary")
        refresh_all_button.connect("clicked", lambda *_args: self.begin_store_action("subscriptions-refresh-all"))
        self.subscription_action_buttons["subscriptions-refresh-all"] = refresh_all_button

        input_row.append(entry)
        input_row.append(add_button)
        input_row.append(refresh_all_button)
        action_panel.append(title)
        action_panel.append(summary)
        action_panel.append(input_row)
        container.append(action_panel)

        body = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=12)
        body.set_vexpand(True)
        add_css_class(body, "native-shell-subscriptions-root")
        subscriptions_panel = self.build_subscription_list_panel()
        subscriptions_panel.set_size_request(420, -1)
        body.append(subscriptions_panel)
        right_column = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        right_column.set_hexpand(True)
        right_column.set_vexpand(True)
        add_css_class(right_column, "native-shell-subscriptions-right")
        right_column.append(self.build_routing_panel())
        body.append(right_column)
        container.append(body)
        return container

    def build_subscription_list_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_hexpand(True)
        panel.set_vexpand(True)
        add_css_class(panel, "native-shell-panel")

        title = self.Gtk.Label(label="Подписки", xalign=0)
        add_css_class(title, "native-shell-card-title")
        copy_label = self.Gtk.Label(
            label="Выберите источник узлов. Длинные URL сокращаются, полное значение доступно во всплывающей подсказке.",
            xalign=0,
        )
        copy_label.set_wrap(True)
        add_css_class(copy_label, "native-shell-muted")
        self.subscription_labels["subscription_copy"] = copy_label

        list_box = self.Gtk.ListBox()
        list_box.set_selection_mode(self.Gtk.SelectionMode.SINGLE)
        list_box.set_activate_on_single_click(True)
        add_css_class(list_box, "native-shell-listbox")
        list_box.connect("row-activated", self.on_subscription_row_activated)
        self.subscription_list_box = list_box

        panel.append(title)
        panel.append(copy_label)
        panel.append(self.build_list_scroller(list_box))
        return panel

    def build_nodes_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_hexpand(True)
        panel.set_vexpand(True)
        add_css_class(panel, "native-shell-metric-card")

        head = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=12)
        head.set_hexpand(True)
        title = self.Gtk.Label(label="Узлы текущей подписки", xalign=0)
        add_css_class(title, "native-shell-card-title")
        self.subscription_labels["node_panel_title"] = title
        head.append(title)

        empty_label = self.Gtk.Label(
            label="Выберите подписку, чтобы здесь появились карточки узлов.",
            xalign=0,
        )
        empty_label.set_wrap(True)
        add_css_class(empty_label, "native-shell-row-copy")
        add_css_class(empty_label, "native-shell-node-empty")
        self.dashboard_node_empty_label = empty_label

        grid_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=DASHBOARD_NODE_CARD_SPACING)
        grid_box.set_hexpand(True)
        grid_box.set_vexpand(True)
        add_css_class(grid_box, "native-shell-node-grid")
        self.dashboard_node_grid_box = grid_box

        scroller = self.build_list_scroller(grid_box)
        scroller.set_vexpand(True)
        scroller.set_visible(False)
        self.dashboard_node_grid_scroller = scroller

        panel.append(head)
        panel.append(empty_label)
        panel.append(scroller)
        return panel

    def build_routing_panel(self):
        panel = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        panel.set_hexpand(True)
        panel.set_vexpand(True)
        add_css_class(panel, "native-shell-panel")

        title = self.Gtk.Label(label="Маршрутизация", xalign=0)
        add_css_class(title, "native-shell-card-title")
        expander_title = self.Gtk.Label(label="Маршрутизация: профиль не выбран", xalign=0)
        add_css_class(expander_title, "native-shell-card-subtitle")

        body = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        body.set_vexpand(True)
        badge = self.Gtk.Label(label="Нет профиля", xalign=0)
        add_css_class(badge, "native-shell-badge")
        add_css_class(badge, "native-shell-chip-warning")
        status_line = self.Gtk.Label(label="Профиль маршрутизации ещё не выбран.", xalign=0)
        status_line.set_wrap(True)
        add_css_class(status_line, "native-shell-muted")
        geodata_line = self.Gtk.Label(label="Наборы GeoIP и GeoSite пока не подготовлены.", xalign=0)
        geodata_line.set_wrap(True)
        add_css_class(geodata_line, "native-shell-card-subtitle")
        self.subscription_labels["routing_badge"] = badge
        self.subscription_labels["routing_expander_title"] = expander_title
        self.subscription_labels["routing_status"] = status_line
        self.subscription_labels["routing_geodata"] = geodata_line

        import_view = self.Gtk.TextView()
        import_view.set_wrap_mode(self.Gtk.WrapMode.WORD_CHAR)
        import_view.set_vexpand(False)
        import_view.set_size_request(-1, 88)
        add_css_class(import_view, "native-shell-input")
        self.routing_import_buffer = import_view.get_buffer()
        import_scroller = self.Gtk.ScrolledWindow()
        import_scroller.set_hexpand(True)
        import_scroller.set_child(import_view)

        action_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        import_button = self.Gtk.Button(label="Импортировать")
        add_css_class(import_button, "native-shell-button-primary")
        import_button.connect("clicked", lambda *_args: self.on_import_routing_requested())
        self.routing_action_buttons["routing-import"] = import_button

        toggle_button = self.Gtk.Button(label="Включить маршрутизацию")
        add_css_class(toggle_button, "native-shell-button-secondary")
        toggle_button.connect("clicked", lambda *_args: self.on_toggle_routing_requested())
        self.routing_action_buttons["routing-toggle"] = toggle_button

        clear_button = self.Gtk.Button(label="Снять активный")
        add_css_class(clear_button, "native-shell-button-secondary")
        clear_button.connect("clicked", lambda *_args: self.begin_store_action("routing-clear-active"))
        self.routing_action_buttons["routing-clear-active"] = clear_button

        action_row.append(import_button)
        action_row.append(toggle_button)
        action_row.append(clear_button)

        list_box = self.Gtk.ListBox()
        list_box.set_selection_mode(self.Gtk.SelectionMode.NONE)
        add_css_class(list_box, "native-shell-listbox")
        self.routing_profile_list_box = list_box

        body.append(badge)
        body.append(status_line)
        body.append(geodata_line)
        body.append(import_scroller)
        body.append(action_row)
        body.append(self.build_list_scroller(list_box))

        panel.append(title)
        panel.append(expander_title)
        panel.append(body)
        return panel

    def build_list_scroller(self, child):
        scrolled = self.Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(child)
        return scrolled

    def clear_list_widget(self, list_widget) -> None:
        child = list_widget.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            list_widget.remove(child)
            child = next_child

    def make_badge(self, label: str, tone: str) -> object:
        badge = self.Gtk.Label(label=label, xalign=0)
        add_css_class(badge, "native-shell-badge")
        add_css_class(badge, f"native-shell-chip-{tone}")
        return badge

    def make_status_badge(self, label: str, tone: str, icon_name: str) -> object:
        badge = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
        add_css_class(badge, "native-shell-badge")
        add_css_class(badge, f"native-shell-chip-{tone}")

        icon = self.Gtk.Image()
        if hasattr(icon, "set_from_icon_name"):
            icon.set_from_icon_name(icon_name)
        elif hasattr(icon, "set_icon_name"):
            icon.set_icon_name(icon_name)
        add_css_class(icon, "native-shell-status-badge-icon")

        text = self.Gtk.Label(label=label, xalign=0)
        add_css_class(text, "native-shell-status-badge-label")

        badge.append(icon)
        badge.append(text)
        return badge

    def make_row_text(self, label: str, css_class: str):
        widget = self.Gtk.Label(label=label, xalign=0)
        widget.set_wrap(True)
        add_css_class(widget, css_class)
        return widget

    def shorten_text(self, value: object, limit: int = 56) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 1)].rstrip()}…"

    def make_trimmed_row_text(self, label: object, css_class: str, *, limit: int = 56):
        raw = str(label or "").strip()
        widget = self.make_row_text(self.shorten_text(raw, limit), css_class)
        if raw and widget.get_label() != raw:
            widget.set_tooltip_text(raw)
        return widget

    def subscription_display_name(self, subscription: dict[str, Any]) -> str:
        name = str(subscription.get("name") or "").strip()
        url = str(subscription.get("url") or "").strip()
        parsed = urlparse(url) if url else None
        host = ""
        if parsed is not None:
            host = parsed.netloc or parsed.path.split("/")[0]
        return host or name or "Без имени"

    def active_subscription_display_name(self) -> str:
        store_payload = self.last_store_payload or {}
        active_profile = active_profile_from_store_snapshot(store_payload) or {}
        subscriptions = subscriptions_from_store_snapshot(store_payload)
        source_subscription_id = str(active_profile.get("source_subscription_id") or "").strip()
        profile_id = str(active_profile.get("id") or "").strip()

        matched_subscription = None
        if source_subscription_id:
            matched_subscription = next(
                (item for item in subscriptions if str(item.get("id") or "").strip() == source_subscription_id),
                None,
            )
        if matched_subscription is None and profile_id:
            matched_subscription = next(
                (item for item in subscriptions if str(item.get("profile_id") or "").strip() == profile_id),
                None,
            )
        if matched_subscription is None:
            matched_subscription = selected_subscription_from_store_snapshot(store_payload, self.selected_subscription_id)
        if not isinstance(matched_subscription, dict):
            return ""
        return self.subscription_display_name(matched_subscription)

    def node_display_name(self, value: object, *, fallback: str = "Без имени") -> str:
        raw = str(value or "").strip()
        if not raw:
            return fallback
        normalized = raw
        while True:
            stripped = NODE_FLAG_PREFIX_RE.sub("", normalized, count=1).strip()
            if stripped == normalized:
                break
            normalized = stripped
        return normalized or fallback

    def dashboard_connection_is_active(
        self,
        summary: dict[str, Any],
        runtime: dict[str, Any],
        processes: dict[str, Any],
    ) -> bool:
        if str(runtime.get("ownership") or "") == "foreign":
            return False
        state = str(summary.get("state") or "stopped")
        return state == "running" or bool(processes.get("xray_alive")) or bool(processes.get("tun_present"))

    def format_connection_duration(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        normalized = raw.replace("Z", "+00:00")
        try:
            started_at = datetime.fromisoformat(normalized)
        except ValueError:
            return ""
        now = datetime.now(started_at.tzinfo) if started_at.tzinfo else datetime.now()
        elapsed = max(0, int((now - started_at).total_seconds()))
        total_days, remainder = divmod(elapsed, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if total_days == 0:
            if hours:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:02d}:{seconds:02d}"

        day_units = [
            ("г", 365),
            ("мес", 30),
            ("нед", 7),
            ("д", 1),
        ]
        prefix_parts: list[str] = []
        remaining_days = total_days
        for suffix, unit_days in day_units:
            value_part, remaining_days = divmod(remaining_days, unit_days)
            if value_part <= 0:
                continue
            prefix_parts.append(f"{value_part}{suffix}")
            if len(prefix_parts) == 2:
                break

        time_suffix = f"{hours}:{minutes:02d}:{seconds:02d}"
        if prefix_parts:
            return " ".join(prefix_parts + [time_suffix])
        return time_suffix

    def parse_dns_servers(self, value: str) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def dashboard_interface_text(self, tun_line: str, dns_value: str) -> str:
        servers = self.parse_dns_servers(dns_value)
        if not servers:
            return f"TUN: {tun_line}\nDNS: —"
        if len(servers) == 1:
            return f"TUN: {tun_line}\nDNS: {servers[0]}"
        rows = [f"TUN: {tun_line}", f"DNS ({len(servers)}):", f"  Основной: {servers[0]}"]
        rows.extend(f"  Доп.: {server}" for server in servers[1:])
        return "\n".join(rows)

    def dashboard_interface_markup(self, tun_line: str, dns_value: str) -> str:
        servers = self.parse_dns_servers(dns_value)
        escaped_tun = escape(tun_line)
        if not servers:
            return f"TUN: {escaped_tun}\nDNS: —"
        if len(servers) == 1:
            return f"TUN: {escaped_tun}\nDNS: {escape(servers[0])}"

        rows = [
            f"TUN: {escaped_tun}",
            f'<span foreground="#B7C0D4" weight="700">DNS ({len(servers)}):</span>',
            (
                '  <span foreground="#7BC4FF" weight="700">Основной:</span> '
                f'<span foreground="#F3F6FB" weight="700">{escape(servers[0])}</span>'
            ),
        ]
        rows.extend(
            '  <span foreground="#B7C0D4">Доп.:</span> '
            f'<span foreground="#F3F6FB">{escape(server)}</span>'
            for server in servers[1:]
        )
        return "\n".join(rows)

    def apply_dashboard_interface_markup(self, tun_line: str, dns_value: str) -> None:
        widget = getattr(self, "dashboard_metrics", {}).get("interface")
        self.set_widget_markup(
            widget,
            self.dashboard_interface_markup(tun_line, dns_value),
            self.dashboard_interface_text(tun_line, dns_value),
        )

    def set_widget_markup(self, widget, markup: str, plain_text: str) -> None:
        if widget is None:
            return
        if hasattr(widget, "set_markup"):
            widget.set_markup(markup)
        elif hasattr(widget, "set_label"):
            widget.set_label(plain_text)

    def dashboard_traffic_text(self, traffic: dict[str, Any]) -> str:
        rx_label = str(traffic.get("rx_rate_label") or "—")
        tx_label = str(traffic.get("tx_rate_label") or "—")
        rx_total = str(traffic.get("rx_total_label") or "—")
        tx_total = str(traffic.get("tx_total_label") or "—")
        return (
            f"Скорость: {rx_label} ↓ · {tx_label} ↑\n"
            f"Объём: {rx_total} ↓ · {tx_total} ↑"
        )

    def dashboard_traffic_markup(self, traffic: dict[str, Any]) -> str:
        rx_label = escape(str(traffic.get("rx_rate_label") or "—"))
        tx_label = escape(str(traffic.get("tx_rate_label") or "—"))
        rx_total = escape(str(traffic.get("rx_total_label") or "—"))
        tx_total = escape(str(traffic.get("tx_total_label") or "—"))
        return (
            f'<span foreground="#B7C0D4" weight="700">Скорость:</span> '
            f'<span foreground="#7BC4FF" weight="700">{rx_label} ↓</span> · '
            f'<span foreground="#FF8A6B" weight="700">{tx_label} ↑</span>\n'
            f'<span foreground="#B7C0D4" weight="700">Объём:</span> '
            f'<span foreground="#7BC4FF" weight="700">{rx_total} ↓</span> · '
            f'<span foreground="#FF8A6B" weight="700">{tx_total} ↑</span>'
        )

    def refresh_dashboard_live_status_line(self) -> None:
        payload = self.last_status_payload or {}
        summary = payload.get("summary", {}) or {}
        runtime = payload.get("runtime", {}) or {}
        processes = payload.get("processes", {}) or {}
        traffic = payload.get("traffic", {}) or {}

        uptime_label = getattr(self, "dashboard_labels", {}).get("hero_uptime")
        traffic_label = getattr(self, "dashboard_labels", {}).get("hero_traffic")
        meta_box = getattr(self, "dashboard_status_meta_box", None)
        active_connection = self.dashboard_connection_is_active(summary, runtime, processes)
        ownership = str(runtime.get("ownership") or "")

        show_uptime = active_connection or ownership == "foreign"
        uptime_text = self.format_connection_duration(runtime.get("connected_since")) if show_uptime else ""
        if uptime_label is not None:
            uptime_label.set_label(f"⏱ {uptime_text}" if uptime_text else "")
            uptime_label.set_visible(bool(uptime_text))

        traffic_text = ""
        rx_label = str(traffic.get("rx_rate_label") or "—")
        tx_label = str(traffic.get("tx_rate_label") or "—")
        rx_total = str(traffic.get("rx_total_label") or "—")
        tx_total = str(traffic.get("tx_total_label") or "—")
        show_traffic = active_connection or ownership == "foreign"
        if show_traffic and any(value != "—" for value in (rx_label, tx_label, rx_total, tx_total)):
            traffic_text = self.dashboard_traffic_text(traffic)
        if traffic_label is not None:
            self.set_widget_markup(traffic_label, self.dashboard_traffic_markup(traffic), traffic_text)
            traffic_label.set_visible(bool(traffic_text))

        if meta_box is not None and hasattr(meta_box, "set_visible"):
            meta_box.set_visible(bool(uptime_text or traffic_text))

    def start_dashboard_uptime_timer(self) -> None:
        if self.dashboard_uptime_source_id is not None or not hasattr(self, "GLib"):
            return
        self.dashboard_uptime_source_id = self.GLib.timeout_add_seconds(1, self.on_dashboard_uptime_tick)

    def on_dashboard_uptime_tick(self) -> bool:
        self.refresh_dashboard_live_status_line()
        return True

    def build_icon_button(self, icon_name: str, tooltip: str, *, label: str | None = None, variant: str = "secondary"):
        button = self.Gtk.Button(label=label) if label else self.Gtk.Button()
        add_css_class(button, f"native-shell-button-{variant}")
        if label is None:
            add_css_class(button, "native-shell-icon-button")
            if hasattr(button, "set_icon_name"):
                button.set_icon_name(icon_name)
            else:
                image = self.Gtk.Image()
                if hasattr(image, "set_from_icon_name"):
                    image.set_from_icon_name(icon_name)
                elif hasattr(image, "set_icon_name"):
                    image.set_icon_name(icon_name)
                button.set_child(image)
        button.set_tooltip_text(tooltip)
        return button

    def build_subscription_menu_button(self, subscription: dict[str, Any], subscription_id: str):
        menu_button = self.Gtk.MenuButton()
        add_css_class(menu_button, "native-shell-button-secondary")
        add_css_class(menu_button, "native-shell-icon-button")
        menu_button.set_tooltip_text("Дополнительные действия для подписки.")
        if hasattr(menu_button, "set_icon_name"):
            menu_button.set_icon_name("open-menu-symbolic")

        popover = self.Gtk.Popover()
        popover_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        popover_box.set_margin_top(8)
        popover_box.set_margin_bottom(8)
        popover_box.set_margin_start(8)
        popover_box.set_margin_end(8)

        toggle_button = self.Gtk.Button(label="Выключить" if subscription.get("enabled", True) else "Включить")
        add_css_class(toggle_button, "native-shell-button-secondary")
        toggle_button.set_sensitive(self.action_in_flight is None)
        toggle_button.connect(
            "clicked",
            self.on_subscription_action_clicked,
            "subscription-toggle",
            subscription_id,
            not bool(subscription.get("enabled", True)),
        )

        delete_button = self.Gtk.Button(label="Удалить")
        add_css_class(delete_button, "native-shell-button-danger")
        delete_button.set_sensitive(self.action_in_flight is None)
        delete_button.connect("clicked", self.on_subscription_action_clicked, "subscription-delete", subscription_id, None)

        popover_box.append(toggle_button)
        popover_box.append(delete_button)
        popover.set_child(popover_box)
        menu_button.set_popover(popover)
        menu_button.set_sensitive(self.action_in_flight is None)
        return menu_button

    def build_subscriptions_empty_row(self, message: str):
        row = self.Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        content = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        add_css_class(content, "native-shell-list-row")
        content.append(self.make_row_text(message, "native-shell-row-copy"))
        row.set_child(content)
        return row

    def node_card_meta_text(self, node: dict[str, Any]) -> str:
        normalized = node.get("normalized", {}) or {}
        address = str(normalized.get("address") or "—")
        port = str(normalized.get("port") or "—")
        protocol = str(node.get("protocol") or "—").strip().upper()
        network = str(normalized.get("network") or "").strip()
        parts = [protocol, f"{address}:{port}"]
        if network:
            parts.append(f"транспорт={network}")
        return " · ".join(parts)

    def build_node_card_placeholder(self):
        spacer = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=0)
        spacer.set_size_request(DASHBOARD_NODE_CARD_WIDTH, DASHBOARD_NODE_CARD_HEIGHT)
        if hasattr(spacer, "set_opacity"):
            spacer.set_opacity(0.0)
        return spacer

    def build_dashboard_node_card(
        self,
        *,
        node: dict[str, Any],
        profile_id: str,
        active_node_id: str | None,
    ):
        node_id = str(node.get("id") or "")
        node_disabled = bool(node.get("parse_error")) or not bool(node.get("enabled", True))
        is_active = bool(active_node_id and node_id == active_node_id)

        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(DASHBOARD_NODE_CARD_WIDTH, DASHBOARD_NODE_CARD_HEIGHT)
        add_css_class(card, "native-shell-node-card")
        if is_active:
            add_css_class(card, "native-shell-node-card-active")
        if node_disabled:
            add_css_class(card, "native-shell-node-card-disabled")
        elif not is_active:
            add_css_class(card, "native-shell-node-card-clickable")

        title = self.make_trimmed_row_text(self.node_display_name(node.get("name")), "native-shell-row-title", limit=34)
        meta = self.make_trimmed_row_text(self.node_card_meta_text(node), "native-shell-row-meta", limit=52)

        badge_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
        if is_active:
            badge_row.append(self.make_badge("текущий", "accent"))
        elif node_disabled:
            badge_row.append(self.make_badge("недоступен", "danger"))
        else:
            badge_row.append(self.make_badge("готов", "success"))

        ping = ping_snapshot_from_status(self.last_status_payload, profile_id, node_id)
        if ping:
            badge_row.append(self.make_badge(str(ping.get("label") or "ping"), "success" if ping.get("ok") else "danger"))
        else:
            badge_row.append(self.make_badge("без ping", "warning"))

        card.append(title)
        card.append(meta)

        if node.get("parse_error"):
            card.append(
                self.make_trimmed_row_text(
                    f"Ошибка: {node['parse_error']}",
                    "native-shell-row-copy",
                    limit=72,
                )
            )

        footer_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        footer_row.set_hexpand(True)
        badge_row.set_hexpand(True)
        footer_row.append(badge_row)

        ping_button = self.build_icon_button("network-wireless-symbolic", "Проверить доступность узла.")
        ping_button.set_sensitive(not node_disabled and self.action_in_flight is None)
        ping_button.connect("clicked", self.on_node_ping_clicked, profile_id, node_id)
        footer_row.append(ping_button)
        card.append(footer_row)

        if not node_disabled and not is_active:
            gesture = self.Gtk.GestureClick()
            if hasattr(gesture, "set_button"):
                gesture.set_button(1)
            gesture.connect("released", self.on_node_card_released, profile_id, node_id)
            card.add_controller(gesture)
        return card

    def render_dashboard_node_grid(
        self,
        nodes: list[dict[str, Any]],
        *,
        profile_id: str,
        active_node_id: str | None,
    ) -> None:
        grid_box = getattr(self, "dashboard_node_grid_box", None)
        if grid_box is None:
            return
        self.clear_list_widget(grid_box)
        for start in range(0, len(nodes), DASHBOARD_NODE_CARD_COLUMNS):
            row_nodes = nodes[start : start + DASHBOARD_NODE_CARD_COLUMNS]
            row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=DASHBOARD_NODE_CARD_SPACING)
            if hasattr(row, "set_halign") and hasattr(self.Gtk, "Align"):
                row.set_halign(self.Gtk.Align.CENTER)
            add_css_class(row, "native-shell-node-grid-row")
            for node in row_nodes:
                row.append(
                    self.build_dashboard_node_card(
                        node=node,
                        profile_id=profile_id,
                        active_node_id=active_node_id,
                    )
                )
            for _index in range(len(row_nodes), DASHBOARD_NODE_CARD_COLUMNS):
                row.append(self.build_node_card_placeholder())
            grid_box.append(row)

    def render_subscriptions_view(self) -> None:
        store_payload = self.last_store_payload or {}
        subscriptions = subscriptions_from_store_snapshot(store_payload)
        selected_subscription = selected_subscription_from_store_snapshot(store_payload, self.selected_subscription_id)
        selected_profile = selected_profile_from_store_snapshot(store_payload, self.selected_subscription_id)
        active_node = active_node_from_store_snapshot(store_payload)
        active_routing_profile = active_routing_profile_from_store_snapshot(store_payload)
        routing = routing_from_store_snapshot(store_payload)
        fresh_subscriptions = sum(1 for item in subscriptions if item.get("last_status") == "ok")

        summary_message = (
            f"{fresh_subscriptions} из {len(subscriptions)} подписок актуальны. Карточки узлов доступны на вкладке `Подключение`."
            if subscriptions
            else "Добавьте первую подписку по URL."
        )
        self.set_subscription_label("summary", summary_message)
        self.set_subscription_label(
            "subscription_copy",
            "Клик по строке выбирает источник узлов; его карточки и действие `Пинг` показываются на вкладке `Подключение`, а выбор узла происходит по нажатию на карточку."
            if subscriptions
            else "Сохранённых подписок пока нет.",
        )

        self.refresh_subscription_rows(subscriptions, selected_subscription)
        self.refresh_node_rows(selected_profile, selected_subscription, active_node)
        self.refresh_routing_panel(routing, active_routing_profile)
        self.refresh_subscriptions_controls()

    def refresh_subscription_rows(
        self,
        subscriptions: list[dict[str, Any]],
        selected_subscription: dict[str, Any] | None,
    ) -> None:
        list_box = self.subscription_list_box
        if list_box is None:
            return

        self.clear_list_widget(list_box)
        if not subscriptions:
            list_box.append(self.build_subscriptions_empty_row("Подписок пока нет."))
            return

        profiles = (self.last_store_payload or {}).get("store", {}).get("profiles", [])
        profile_map = {
            str(profile.get("id")): profile
            for profile in profiles
            if isinstance(profile, dict) and profile.get("id")
        }
        selected_id = str(selected_subscription.get("id")) if selected_subscription else None
        selected_row = None

        for subscription in subscriptions:
            profile = profile_map.get(str(subscription.get("profile_id")))
            row = self.Gtk.ListBoxRow()
            row.subscription_id = str(subscription.get("id") or "")
            row.set_selectable(True)
            row.set_activatable(True)

            content = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
            add_css_class(content, "native-shell-list-row")

            header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
            header.set_hexpand(True)
            title_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=4)
            title_box.set_hexpand(True)
            title_box.append(self.make_trimmed_row_text(self.subscription_display_name(subscription), "native-shell-row-title", limit=38))
            title_box.append(self.make_trimmed_row_text(str(subscription.get("url") or "—"), "native-shell-row-meta", limit=64))

            status_tone = "success"
            status_label = "актуальна"
            if subscription.get("last_status") == "error":
                status_tone = "danger"
                status_label = "ошибка"
            elif subscription.get("last_status") != "ok":
                status_tone = "warning"
                status_label = "ожидает обновления"
            node_count = len(profile.get("nodes", [])) if isinstance(profile, dict) else 0
            badge_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
            badge_row.append(self.make_badge(status_label, status_tone))
            badge_row.append(self.make_badge(f"узлов {node_count}", "accent"))

            action_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
            refresh_button = self.build_icon_button("view-refresh-symbolic", "Обновить подписку.")
            refresh_button.set_sensitive(self.action_in_flight is None)
            refresh_button.connect("clicked", self.on_subscription_action_clicked, "subscription-refresh", row.subscription_id, None)
            action_row.append(refresh_button)
            action_row.append(self.build_subscription_menu_button(subscription, row.subscription_id))

            header.append(title_box)
            header.append(badge_row)
            content.append(header)
            if subscription.get("last_error"):
                content.append(self.make_row_text(str(subscription.get("last_error")), "native-shell-row-copy"))
            else:
                timestamp = subscription.get("last_success_at")
                content.append(
                    self.make_row_text(
                        f"Последнее обновление: {timestamp or 'ещё не выполнялось'}",
                        "native-shell-row-copy",
                    )
                )
            header.append(action_row)
            row.set_child(content)
            list_box.append(row)

            if selected_id and row.subscription_id == selected_id:
                selected_row = row

        if selected_row is not None:
            list_box.select_row(selected_row)

    def refresh_node_rows(
        self,
        selected_profile: dict[str, Any] | None,
        selected_subscription: dict[str, Any] | None,
        active_node: dict[str, Any] | None,
    ) -> None:
        grid_box = getattr(self, "dashboard_node_grid_box", None)
        empty_label = getattr(self, "dashboard_node_empty_label", None)
        grid_scroller = getattr(self, "dashboard_node_grid_scroller", None)
        if grid_box is None:
            return

        if not selected_subscription or not selected_profile:
            self.set_subscription_label("node_panel_title", "Узлы текущей подписки")
            self.clear_list_widget(grid_box)
            if empty_label is not None:
                empty_label.set_label("Для выбора узла сначала укажите источник на вкладке `Подписки`.")
                empty_label.set_visible(True)
            if grid_scroller is not None:
                grid_scroller.set_visible(False)
            return

        nodes = selected_profile.get("nodes", []) if isinstance(selected_profile.get("nodes"), list) else []
        self.set_subscription_label("node_panel_title", "Узлы текущей подписки")

        if not nodes:
            self.clear_list_widget(grid_box)
            if empty_label is not None:
                empty_label.set_label("В выбранной подписке пока нет узлов.")
                empty_label.set_visible(True)
            if grid_scroller is not None:
                grid_scroller.set_visible(False)
            return

        active_node_id = str(active_node.get("id")) if active_node else None
        profile_id = str(selected_profile.get("id") or "")
        self.render_dashboard_node_grid(nodes, profile_id=profile_id, active_node_id=active_node_id)
        if empty_label is not None:
            empty_label.set_visible(False)
        if grid_scroller is not None:
            grid_scroller.set_visible(True)

    def refresh_routing_panel(
        self,
        routing: dict[str, Any],
        active_routing_profile: dict[str, Any] | None,
    ) -> None:
        enabled = bool(routing.get("enabled"))
        ready = bool(routing.get("runtime_ready"))
        profiles = routing_profiles_from_store_snapshot(self.last_store_payload)
        geodata = routing.get("geodata") or {}
        subscription_names = {
            str(item.get("id") or ""): str(item.get("name") or "")
            for item in subscriptions_from_store_snapshot(self.last_store_payload)
            if item.get("id")
        }

        badge_value = "Нет профиля"
        badge_tone = "warning"
        if enabled and active_routing_profile and ready:
            badge_value = "Включена"
            badge_tone = "success"
        elif enabled:
            badge_value = "Ошибка"
            badge_tone = "danger"
        elif active_routing_profile:
            badge_value = "Выключена"
            badge_tone = "accent"

        self.set_subscription_label("routing_badge", badge_value, tone=badge_tone)
        if active_routing_profile:
            mode_label = "через прокси" if active_routing_profile.get("global_proxy") else "с прямым обходом"
            status_text = (
                f"Активен профиль '{active_routing_profile['name']}', применяется {active_routing_profile.get('supported_entry_count', 0)} правил, режим {mode_label}."
                if enabled and ready
                else f"Выбран профиль '{active_routing_profile['name']}', правил {active_routing_profile.get('supported_entry_count', 0)}, режим {mode_label}."
            )
            expander_title = f"Маршрутизация: {active_routing_profile['name']}"
        else:
            status_text = "Профиль маршрутизации ещё не выбран."
            expander_title = "Маршрутизация: отключена"
        self.set_subscription_label("routing_status", status_text)
        self.set_subscription_label("routing_expander_title", expander_title)

        geodata_text = "Наборы GeoIP и GeoSite пока не подготовлены."
        if geodata.get("ready"):
            geodata_text = (
                f"Наборы GeoIP и GeoSite готовы: `geoip.dat` и `geosite.dat` доступны в {geodata.get('asset_dir') or 'каталоге данных'}."
            )
        elif geodata.get("status") == "error":
            geodata_text = f"Наборы GeoIP и GeoSite не готовы: {geodata.get('error') or 'ошибка загрузки'}."
        self.set_subscription_label("routing_geodata", geodata_text)

        toggle_button = self.routing_action_buttons.get("routing-toggle")
        if toggle_button is not None:
            toggle_button.set_label("Выключить маршрутизацию" if enabled else "Включить маршрутизацию")

        list_box = self.routing_profile_list_box
        if list_box is None:
            return

        self.clear_list_widget(list_box)
        if not profiles:
            list_box.append(self.build_subscriptions_empty_row("Профилей маршрутизации пока нет."))
            return

        active_id = str(active_routing_profile.get("id")) if active_routing_profile else None
        for profile in profiles:
            row = self.Gtk.ListBoxRow()
            row.set_selectable(False)
            row.set_activatable(False)
            content = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
            add_css_class(content, "native-shell-list-row")

            header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
            title_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=4)
            title_box.set_hexpand(True)
            title_box.append(self.make_row_text(str(profile.get("name") or "Без имени"), "native-shell-row-title"))
            source_subscription_name = subscription_names.get(str(profile.get("source_subscription_id") or ""), "")
            meta = [
                f"правил {profile.get('supported_entry_count', 0)}",
                "через прокси" if profile.get("global_proxy") else "с прямым обходом",
                f"формат {profile.get('source_format') or 'json'}",
            ]
            source_meta = [
                "авто из подписки" if profile.get("auto_managed") else "ручной импорт",
                f"подписка {source_subscription_name}" if source_subscription_name else "",
                f"providerId {profile.get('provider_id')}" if profile.get("provider_id") else "",
                f"режим {profile.get('activation_mode')}" if profile.get("activation_mode") not in {None, '', 'manual'} else "",
            ]
            title_box.append(self.make_row_text(" · ".join(meta), "native-shell-row-meta"))
            title_box.append(
                self.make_row_text(
                    " · ".join(part for part in source_meta if part) or "Источник не указан.",
                    "native-shell-row-meta",
                )
            )

            badge_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
            is_active = active_id and str(profile.get("id")) == active_id
            disabled = not bool(profile.get("enabled", True))
            if is_active and enabled and ready:
                badge_row.append(self.make_badge("применяется", "success"))
            elif is_active:
                badge_row.append(self.make_badge("выбран", "accent"))
            elif disabled:
                badge_row.append(self.make_badge("отключён", "danger"))
            else:
                badge_row.append(self.make_badge("готов", "success"))

            action_row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
            if not disabled:
                activate_button = self.Gtk.Button(label="Текущий" if is_active else "Сделать текущим")
                add_css_class(activate_button, "native-shell-button-secondary")
                activate_button.set_sensitive(self.action_in_flight is None)
                activate_button.connect("clicked", self.on_routing_profile_action_clicked, "routing-activate-profile", str(profile.get("id") or ""), None)
                action_row.append(activate_button)

            toggle_button = self.Gtk.Button(label="Включить профиль" if disabled else "Отключить профиль")
            add_css_class(toggle_button, "native-shell-button-danger" if not disabled else "native-shell-button-secondary")
            toggle_button.set_sensitive(self.action_in_flight is None)
            toggle_button.connect(
                "clicked",
                self.on_routing_profile_action_clicked,
                "routing-toggle-profile",
                str(profile.get("id") or ""),
                disabled,
            )
            action_row.append(toggle_button)

            header.append(title_box)
            header.append(badge_row)
            content.append(header)
            content.append(action_row)
            row.set_child(content)
            list_box.append(row)

    def set_subscription_label(self, key: str, value: str, *, tone: str | None = None) -> None:
        label = self.subscription_labels.get(key)
        if label is None:
            return
        label.set_label(value)
        if tone is not None:
            for current_tone in ("success", "warning", "danger", "accent"):
                if hasattr(label, "remove_css_class"):
                    label.remove_css_class(f"native-shell-chip-{current_tone}")
            add_css_class(label, f"native-shell-chip-{tone}")

    def on_subscription_row_activated(self, _list_box, row) -> None:
        if self.subscription_row_click_suppressed or self.action_in_flight:
            self.subscription_row_click_suppressed = False
            return
        subscription_id = str(getattr(row, "subscription_id", "") or "")
        if not subscription_id:
            return
        self.selected_subscription_id = subscription_id
        self.render_subscriptions_view()

    def reset_subscription_row_suppression(self) -> bool:
        self.subscription_row_click_suppressed = False
        return False

    def on_subscription_action_clicked(self, _button, action_id: str, subscription_id: str, enabled_value: object) -> None:
        self.subscription_row_click_suppressed = True
        self.GLib.idle_add(self.reset_subscription_row_suppression)
        kwargs: dict[str, Any] = {"subscription_id": subscription_id}
        if action_id == "subscription-toggle":
            kwargs["enabled"] = bool(enabled_value)
        self.begin_store_action(action_id, **kwargs)

    def on_node_row_activated(self, _list_box, row) -> None:
        if self.node_row_click_suppressed or self.action_in_flight:
            self.node_row_click_suppressed = False
            return
        profile_id = str(getattr(row, "profile_id", "") or "")
        node_id = str(getattr(row, "node_id", "") or "")
        if not profile_id or not node_id or bool(getattr(row, "node_disabled", False)):
            return
        self.begin_store_action("node-activate", profile_id=profile_id, node_id=node_id)

    def reset_node_row_suppression(self) -> bool:
        self.node_row_click_suppressed = False
        return False

    def on_node_ping_clicked(self, _button, profile_id: str, node_id: str) -> None:
        self.node_row_click_suppressed = True
        self.GLib.idle_add(self.reset_node_row_suppression)
        self.begin_store_action("node-ping", profile_id=profile_id, node_id=node_id)

    def on_node_activate_clicked(self, _button, profile_id: str, node_id: str) -> None:
        self.begin_store_action("node-activate", profile_id=profile_id, node_id=node_id)

    def on_node_card_released(self, _gesture, _press_count: int, _x: float, _y: float, profile_id: str, node_id: str) -> None:
        if self.node_row_click_suppressed or self.action_in_flight:
            self.node_row_click_suppressed = False
            return
        self.begin_store_action("node-activate", profile_id=profile_id, node_id=node_id)

    def on_routing_profile_action_clicked(self, _button, action_id: str, profile_id: str, enabled_value: object) -> None:
        kwargs: dict[str, Any] = {"profile_id": profile_id}
        if action_id == "routing-toggle-profile":
            kwargs["enabled"] = bool(enabled_value)
        self.begin_store_action(action_id, **kwargs)

    def on_add_subscription_requested(self) -> None:
        if self.subscription_url_entry is None:
            return
        url = self.subscription_url_entry.get_text().strip()
        if not url:
            self.set_status("Укажите URL подписки.")
            self.append_log("subscriptions", "Добавление подписки отклонено: URL пуст.")
            return
        self.begin_store_action("subscriptions-add", name="", url=url)

    def routing_import_text(self) -> str:
        if self.routing_import_buffer is None:
            return ""
        start_iter = self.routing_import_buffer.get_start_iter()
        end_iter = self.routing_import_buffer.get_end_iter()
        return self.routing_import_buffer.get_text(start_iter, end_iter, True).strip()

    def on_import_routing_requested(self) -> None:
        text = self.routing_import_text()
        if not text:
            self.set_status("Вставьте профиль маршрутизации для импорта.")
            self.append_log("routing", "Импорт маршрутизации отклонён: поле пустое.")
            return
        self.begin_store_action("routing-import", text=text)

    def on_toggle_routing_requested(self) -> None:
        routing = routing_from_store_snapshot(self.last_store_payload)
        self.begin_store_action("routing-toggle", enabled=not bool(routing.get("enabled")))

    def refresh_subscriptions_controls(self) -> None:
        busy = self.action_in_flight is not None
        subscriptions = subscriptions_from_store_snapshot(self.last_store_payload)
        active_routing_profile = active_routing_profile_from_store_snapshot(self.last_store_payload)
        routing = routing_from_store_snapshot(self.last_store_payload)

        if self.subscription_url_entry is not None:
            self.subscription_url_entry.set_sensitive(not busy)
        for action_id, button in self.subscription_action_buttons.items():
            if action_id == "subscriptions-refresh-all":
                button.set_sensitive(not busy and bool(subscriptions))
            else:
                button.set_sensitive(not busy)
        for action_id, button in self.routing_action_buttons.items():
            if action_id == "routing-toggle":
                button.set_sensitive(not busy and (bool(active_routing_profile) or bool(routing.get("enabled"))))
            elif action_id == "routing-clear-active":
                button.set_sensitive(not busy and bool(active_routing_profile))
            else:
                button.set_sensitive(not busy)

    def build_log_page(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        add_css_class(container, "native-shell-panel")

        title = self.Gtk.Label(label="Диагностика", xalign=0)
        add_css_class(title, "native-shell-card-title")
        summary = self.Gtk.Label(
            label="Сводка подключения и журнал разделены, чтобы технические детали оставались читаемыми и не захламляли экран.",
            xalign=0,
        )
        summary.set_wrap(True)
        add_css_class(summary, "native-shell-muted")
        container.append(title)
        container.append(summary)

        view_stack = self.Gtk.Stack()
        view_stack.set_hexpand(True)
        view_stack.set_vexpand(True)
        view_stack.set_transition_type(self.Gtk.StackTransitionType.CROSSFADE)
        switcher = self.Gtk.StackSwitcher()
        switcher.set_stack(view_stack)

        view_stack.add_titled(self.build_diagnostics_panel(), "diagnostic-summary", "Сводка")
        view_stack.add_titled(self.build_log_journal_panel(), "diagnostic-log", "Журнал")

        container.append(switcher)
        container.append(view_stack)
        return container

    def build_log_journal_panel(self):
        container = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)

        self.log_summary_label = self.Gtk.Label(
            label="Ошибок пока нет. Последних действий тоже нет.",
            xalign=0,
        )
        self.log_summary_label.set_wrap(True)
        add_css_class(self.log_summary_label, "native-shell-muted")

        self.log_meta_label = self.Gtk.Label(
            label="Фильтр: Все. Источники появятся после первого обновления.",
            xalign=0,
        )
        self.log_meta_label.set_wrap(True)
        add_css_class(self.log_meta_label, "native-shell-muted")

        self.log_export_label = self.Gtk.Label(
            label=f"Экспорт: {self.resolve_log_export_dir()}",
            xalign=0,
        )
        self.log_export_label.set_wrap(True)
        add_css_class(self.log_export_label, "native-shell-muted")

        toolbar = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_hexpand(True)

        for filter_id in NATIVE_SHELL_LOG_FILTER_VALUES:
            button = self.Gtk.Button(label=native_shell_log_filter_label(filter_id))
            add_css_class(button, "native-shell-button-secondary")
            button.connect("clicked", lambda *_args, value=filter_id: self.on_log_filter_selected(value))
            self.log_filter_buttons[filter_id] = button
            toolbar.append(button)

        copy_button = self.Gtk.Button(label="Скопировать")
        add_css_class(copy_button, "native-shell-button-secondary")
        copy_button.connect("clicked", lambda *_args: self.copy_visible_log_to_clipboard())
        self.log_copy_button = copy_button
        toolbar.append(copy_button)

        export_button = self.Gtk.Button(label="Экспорт")
        add_css_class(export_button, "native-shell-button-primary")
        export_button.connect("clicked", lambda *_args: self.export_visible_log())
        self.log_export_button = export_button
        toolbar.append(export_button)

        scrolled = self.Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        add_css_class(scrolled, "native-shell-log-scroller")
        text_view = self.Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        add_css_class(text_view, "native-shell-log-view")
        self.log_buffer = text_view.get_buffer()
        self.refresh_log_view()
        scrolled.set_child(text_view)

        container.append(self.log_summary_label)
        container.append(self.log_meta_label)
        container.append(self.log_export_label)
        container.append(toolbar)
        container.append(scrolled)
        return container

    def on_log_filter_selected(self, level_filter: str) -> None:
        self.log_filter = normalize_native_shell_log_filter(level_filter)
        self.refresh_log_view()

    def current_bundle_log_entries(self) -> list[dict[str, Any]]:
        return log_entries_from_status(getattr(self, "last_status_payload", None))

    def current_shell_log_entries(self) -> list[dict[str, Any]]:
        entries = getattr(self, "shell_log_entries", None)
        return list(entries) if isinstance(entries, list) else []

    def visible_log_entries(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        normalized_filter = normalize_native_shell_log_filter(getattr(self, "log_filter", "all"))
        shell_entries = filter_log_entries(self.current_shell_log_entries(), normalized_filter)
        bundle_entries = filter_log_entries(self.current_bundle_log_entries(), normalized_filter)
        return shell_entries, bundle_entries

    def visible_log_text(self) -> str:
        normalized_filter = normalize_native_shell_log_filter(getattr(self, "log_filter", "all"))
        return build_native_shell_log_text(
            bundle_entries=self.current_bundle_log_entries(),
            shell_entries=self.current_shell_log_entries(),
            level_filter=normalized_filter,
        )

    def resolve_log_export_dir(self) -> Path:
        runtime_service = getattr(self, "runtime_service", None)
        context = getattr(runtime_service, "context", None)
        log_dir = getattr(context, "log_dir", None)
        if isinstance(log_dir, Path):
            return log_dir
        log_path = getattr(self, "log_path", None)
        if isinstance(log_path, Path):
            return log_path.parent
        return GUI_DIR.parent / "logs"

    def copy_visible_log_to_clipboard(self) -> None:
        shell_entries, bundle_entries = self.visible_log_entries()
        if not shell_entries and not bundle_entries:
            self.set_status("Видимый лог пуст: копировать нечего.")
            return

        display = self.Gdk.Display.get_default() if hasattr(self, "Gdk") else None
        if display is None:
            message = "Буфер обмена недоступен: GTK display не активен."
            self.set_status(message)
            self.append_log("log", message)
            return

        clipboard = display.get_clipboard()
        provider = self.Gdk.ContentProvider.new_for_value(self.visible_log_text())
        if not clipboard.set_content(provider):
            message = "Буфер обмена отклонил содержимое лога."
            self.set_status(message)
            self.append_log("log", message)
            return

        message = "Видимый лог скопирован в буфер обмена."
        self.set_status(message)
        self.append_log("log", message)

    def export_visible_log(self) -> None:
        shell_entries, bundle_entries = self.visible_log_entries()
        if not shell_entries and not bundle_entries:
            self.set_status("Видимый лог пуст: экспортировать нечего.")
            return

        export_dir = self.resolve_log_export_dir()
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"native-shell-log-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        export_path.write_text(self.visible_log_text() + "\n", encoding="utf-8")
        self.last_log_export_path = export_path
        message = f"Видимый лог экспортирован: {export_path}"
        self.set_status(message)
        self.append_log("log", message)
        self.refresh_log_view()

    def build_settings_window(self):
        window = self.Gtk.Window(transient_for=self.window, title="Настройки интерфейса")
        window.set_default_size(480, 340)
        window.set_modal(False)

        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=16)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        add_css_class(root, "native-shell-root")

        intro = self.Gtk.Label(
            label="Только параметры интерфейса: трей, локальный журнал и фиксированный тёмный режим.",
            xalign=0,
        )
        intro.set_wrap(True)
        add_css_class(intro, "native-shell-muted")
        root.append(intro)

        switches = (
            ("file_logs_enabled", "Файловое логирование", "Сохранять журнал интерфейса в пользовательском каталоге приложения."),
            ("close_to_tray", "Закрытие окна уводит в трей", "Используется только если трей действительно доступен."),
            ("start_minimized_to_tray", "Старт свёрнутым в трей", "Если трей недоступен, окно всё равно откроется обычным способом."),
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
                "Сейчас интерфейс работает только в тёмном режиме. "
                "Сохранённые старые значения `system` и `light` автоматически приводятся к тёмному контракту."
            ),
            xalign=0,
        )
        theme_hint.set_wrap(True)
        add_css_class(theme_hint, "native-shell-muted")
        theme_value = self.Gtk.Label(label=native_shell_theme_label(self.settings.theme), xalign=0)
        add_css_class(theme_value, "native-shell-card-subtitle")
        theme_box.append(theme_title)
        theme_box.append(theme_hint)
        theme_box.append(theme_value)
        root.append(theme_box)

        tray_note = self.Gtk.Label(
            label=f"Состояние трея: {self.tray_support.reason}",
            xalign=0,
        )
        tray_note.set_wrap(True)
        add_css_class(tray_note, "native-shell-muted")
        root.append(tray_note)

        log_path_label = self.Gtk.Label(label=f"Локальный лог: {self.log_path}", xalign=0)
        log_path_label.set_wrap(True)
        add_css_class(log_path_label, "native-shell-muted")
        root.append(log_path_label)

        update_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        update_title = self.Gtk.Label(label="Обновление ядра Xray", xalign=0)
        add_css_class(update_title, "native-shell-card-title")
        update_hint = self.Gtk.Label(
            label=(
                "Обновляет только системный бинарник xray-core через официальный Xray-install. "
                "Код приложения и подписки не меняются; активное подключение нужно отключить вручную."
            ),
            xalign=0,
        )
        update_hint.set_wrap(True)
        add_css_class(update_hint, "native-shell-muted")
        update_button = self.Gtk.Button(label="Обновить ядро Xray")
        add_css_class(update_button, "native-shell-button-secondary")
        update_button.set_tooltip_text("Запустить обновление ядра Xray через pkexec.")
        update_button.connect("clicked", self.on_update_xray_core_clicked)
        update_feedback = self.Gtk.Label(label="Готово к обновлению ядра Xray.", xalign=0)
        update_feedback.set_wrap(True)
        add_css_class(update_feedback, "native-shell-action-feedback")
        self.settings_update_button = update_button
        self.settings_update_feedback_label = update_feedback
        update_box.append(update_title)
        update_box.append(update_hint)
        update_box.append(update_button)
        update_box.append(update_feedback)
        root.append(update_box)

        close_button = self.Gtk.Button(label="Закрыть")
        close_button.connect("clicked", lambda *_args: window.hide())
        root.append(close_button)

        window.set_child(root)
        self.refresh_settings_controls()
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

    def on_update_xray_core_clicked(self, _button) -> None:
        self.begin_runtime_action("update-xray-core", source="settings")

    def action_label(self, action_id: str) -> str:
        return native_shell_action_label(action_id)

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
            current_label = self.action_label(self.action_in_flight)
            self.set_status(f"Уже выполняется действие: {current_label}.")
            self.append_log(source, f"{self.action_label(action_id)} пропущен: занято действием {current_label}.")
            if action_id in {"capture-diagnostics", "cleanup-artifacts"}:
                self.set_diagnostic_action_feedback("busy", f"Уже выполняется: {current_label}.")
            if action_id == "update-xray-core":
                self.set_settings_update_feedback("busy", f"Уже выполняется: {current_label}.")
            return

        action_label = self.action_label(action_id)
        self.action_in_flight = action_id
        self.set_status(f"{action_label}: выполняется через общий сервисный слой…")
        if action_id in {"capture-diagnostics", "cleanup-artifacts"}:
            self.set_diagnostic_action_feedback("busy", f"{action_label}: выполняется.")
        if action_id == "update-xray-core":
            self.set_settings_update_feedback("busy", "Обновление ядра Xray выполняется.")
        self.append_log(source, f"{action_label}: действие передано в службу подключения.")
        self.refresh_dashboard_controls()
        self.refresh_settings_controls()
        self.refresh_subscriptions_controls()
        self.render_subscriptions_view()
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
            "takeover-runtime": self.runtime_service.takeover_runtime,
            "cleanup-artifacts": self.runtime_service.cleanup_runtime_artifacts,
            "capture-diagnostics": self.runtime_service.capture_diagnostics,
            "update-xray-core": self.runtime_service.update_xray_core,
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
        action_label = self.action_label(action_id)
        self.action_in_flight = None
        if ok:
            status_payload = payload if isinstance(payload, dict) else {}
            self.apply_status_payload(status_payload)
            message = str(status_payload.get("last_action", {}).get("message") or f"{action_label}: выполнено.")
            self.set_status(message)
            if action_id in {"capture-diagnostics", "cleanup-artifacts"}:
                self.set_diagnostic_action_feedback("success", message)
            if action_id == "update-xray-core":
                self.set_settings_update_feedback("success", message)
            self.append_log(source, f"{action_label}: {message}")
        else:
            message = str(payload)
            self.set_status(f"{action_label}: {message}")
            if action_id in {"capture-diagnostics", "cleanup-artifacts"}:
                self.set_diagnostic_action_feedback("error", f"{action_label}: {message}")
            if action_id == "update-xray-core":
                self.set_settings_update_feedback("error", f"{action_label}: {message}")
            self.append_log(source, f"{action_label}: ошибка: {message}")
            self.request_status_refresh(reason=f"{action_id}-error")
        self.refresh_dashboard_controls()
        self.refresh_settings_controls()
        self.refresh_subscriptions_controls()
        return False

    def begin_store_action(self, action_id: str, *, source: str = "window", **kwargs: Any) -> None:
        if self.action_in_flight:
            current_label = self.action_label(self.action_in_flight)
            self.set_status(f"Уже выполняется действие: {current_label}.")
            self.append_log(source, f"{self.action_label(action_id)} пропущен: занято действием {current_label}.")
            return

        action_label = self.action_label(action_id)
        self.action_in_flight = action_id
        self.set_status(f"{action_label}: выполняется через общий сервисный слой…")
        self.append_log(source, f"{action_label}: действие передано в общий сервис подписок и маршрутизации.")
        self.refresh_dashboard_controls()
        self.refresh_settings_controls()
        self.refresh_subscriptions_controls()
        self.render_subscriptions_view()
        worker = threading.Thread(
            target=self.run_store_action_worker,
            args=(action_id, source, kwargs),
            daemon=True,
        )
        worker.start()

    def run_store_action_worker(self, action_id: str, source: str, kwargs: dict[str, Any]) -> None:
        action_handlers = {
            "subscriptions-add": lambda: self.runtime_service.add_subscription(str(kwargs.get("name", "")), str(kwargs.get("url", ""))),
            "subscriptions-refresh-all": self.runtime_service.refresh_all_subscriptions,
            "subscription-refresh": lambda: self.runtime_service.refresh_subscription(str(kwargs["subscription_id"])),
            "subscription-toggle": lambda: self.runtime_service.update_subscription(
                str(kwargs["subscription_id"]),
                enabled=bool(kwargs["enabled"]),
            ),
            "subscription-delete": lambda: self.runtime_service.delete_subscription(str(kwargs["subscription_id"])),
            "node-activate": lambda: self.runtime_service.activate_selection(str(kwargs["profile_id"]), str(kwargs["node_id"])),
            "node-ping": lambda: self.runtime_service.ping_node_by_id(str(kwargs["profile_id"]), str(kwargs["node_id"])),
            "routing-import": lambda: self.runtime_service.import_routing_profile(str(kwargs["text"])),
            "routing-toggle": lambda: self.runtime_service.set_routing_enabled(bool(kwargs["enabled"])),
            "routing-clear-active": self.runtime_service.clear_active_routing_profile,
            "routing-activate-profile": lambda: self.runtime_service.activate_routing_profile(str(kwargs["profile_id"])),
            "routing-toggle-profile": lambda: self.runtime_service.update_routing_profile_enabled(
                str(kwargs["profile_id"]),
                enabled=bool(kwargs["enabled"]),
            ),
        }
        handler = action_handlers.get(action_id)
        if handler is None:
            self.GLib.idle_add(self.finish_store_action, action_id, source, False, "Неизвестное действие.")
            return

        try:
            payload = handler()
        except Exception as exc:
            self.GLib.idle_add(self.finish_store_action, action_id, source, False, str(exc))
            return
        self.GLib.idle_add(self.finish_store_action, action_id, source, True, payload)

    def finish_store_action(self, action_id: str, source: str, ok: bool, payload: object) -> bool:
        action_label = self.action_label(action_id)
        self.action_in_flight = None
        if ok and isinstance(payload, dict):
            if action_id == "subscriptions-add":
                subscription = payload.get("subscription")
                if isinstance(subscription, dict) and subscription.get("id"):
                    self.selected_subscription_id = str(subscription["id"])
                if self.subscription_url_entry is not None:
                    self.subscription_url_entry.set_text("")
            elif action_id == "routing-import" and self.routing_import_buffer is not None:
                self.routing_import_buffer.set_text("")

            if "store" in payload:
                self.apply_combined_snapshot(payload)
            else:
                status_payload = payload.get("status")
                if isinstance(status_payload, dict):
                    self.apply_status_payload(status_payload)
            message = str(
                payload.get("message")
                or payload.get("status", {}).get("last_action", {}).get("message")
                or payload.get("last_action", {}).get("message")
                or f"{action_label}: выполнено."
            )
            self.set_status(message)
            self.append_log(source, f"{action_label}: {message}")
        else:
            message = str(payload)
            self.set_status(f"{action_label}: {message}")
            self.append_log(source, f"{action_label}: ошибка: {message}")
            self.request_status_refresh(reason=f"{action_id}-error")
        self.refresh_dashboard_controls()
        self.refresh_settings_controls()
        self.refresh_subscriptions_controls()
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
            payload = self.runtime_service.collect_store_snapshot()
        except Exception as exc:
            self.GLib.idle_add(self.finish_status_refresh, reason, False, str(exc), silent)
            return
        self.GLib.idle_add(self.finish_status_refresh, reason, True, payload, silent)

    def finish_status_refresh(self, reason: str, ok: bool, payload: object, silent: bool) -> bool:
        self.status_refresh_in_flight = False
        if ok and isinstance(payload, dict):
            self.apply_combined_snapshot(payload)
            if not silent and self.action_in_flight is None:
                status_payload = payload.get("status") if isinstance(payload.get("status"), dict) else {}
                self.set_status(self.status_message_from_payload(status_payload))
            return False

        if not silent:
            message = str(payload)
            self.set_status(f"Не удалось обновить снимок подключения: {message}")
            self.append_log("status", f"Ошибка обновления экранов подключения и выбора узлов ({reason}): {message}")
        self.refresh_dashboard_controls()
        self.refresh_subscriptions_controls()
        return False

    def apply_status_payload(self, payload: dict[str, Any]) -> None:
        self.last_status_payload = payload
        self.update_dashboard_from_status(payload)
        self.render_subscriptions_view()
        self.refresh_log_view()

    def apply_store_payload(self, payload: dict[str, Any]) -> None:
        self.last_store_payload = payload
        self.selected_subscription_id = resolve_selected_subscription_id(payload, self.selected_subscription_id)
        self.render_subscriptions_view()
        self.refresh_log_view()

    def apply_combined_snapshot(self, payload: dict[str, Any]) -> None:
        status_payload = payload.get("status") if isinstance(payload.get("status"), dict) else None
        store_payload = payload.get("store") if isinstance(payload.get("store"), dict) else None

        if status_payload is not None:
            self.last_status_payload = status_payload
            self.update_dashboard_from_status(status_payload)
        if store_payload is not None:
            self.last_store_payload = store_payload
            self.selected_subscription_id = resolve_selected_subscription_id(store_payload, self.selected_subscription_id)
        self.render_subscriptions_view()
        self.refresh_log_view()

    def status_message_from_payload(self, payload: dict[str, Any]) -> str:
        last_action = payload.get("last_action", {}) or {}
        if last_action.get("timestamp") and last_action.get("message"):
            return str(last_action["message"])
        runtime = payload.get("runtime", {}) or {}
        if runtime.get("start_blocked"):
            if str(runtime.get("ownership") or "") == "foreign":
                return "Снимок состояния обновлён."
            return self.concise_runtime_block_message(runtime, for_status=True)
        return str(payload.get("summary", {}).get("description") or "Состояние обновлено.")

    def concise_runtime_block_message(
        self,
        runtime: dict[str, Any],
        *,
        for_action_hint: bool = False,
        for_status: bool = False,
    ) -> str:
        ownership = str(runtime.get("ownership") or "")
        if ownership == "foreign":
            if for_status:
                return "Сейчас подключением управляет другой экземпляр Subvost."
            if for_action_hint:
                return "Откройте диагностику: там виден путь к активному экземпляру и можно снять дамп."
            return "Это окно не управляет чужим подключением."
        if ownership == "unknown":
            if for_status:
                return "Источник активного подключения пока не удалось подтвердить."
            if for_action_hint:
                return "Откройте диагностику: там видны детали конфликта и текущие служебные файлы подключения."
            return "Управление подключением заблокировано, пока источник не подтверждён."
        message = str(runtime.get("next_start_reason") or runtime.get("control_message") or "").strip()
        if for_action_hint and message:
            return message
        if message:
            return message
        return "Запуск сейчас заблокирован."

    def user_facing_runtime_state_label(self, summary: dict[str, Any], runtime: dict[str, Any]) -> str:
        ownership = str(runtime.get("ownership") or "")
        if ownership == "foreign":
            return "Подключением управляет другой экземпляр"
        if ownership == "unknown" and runtime.get("start_blocked"):
            return "Источник подключения не подтверждён"
        return str(summary.get("label") or "—")

    def show_page(self, page_id: str) -> None:
        if self.stack is not None:
            self.stack.set_visible_child_name(page_id)

    def on_takeover_requested(self, _button) -> None:
        self.begin_runtime_action("takeover-runtime", source="window")

    def on_cleanup_artifacts_clicked(self, _button) -> None:
        self.begin_runtime_action("cleanup-artifacts", source="diagnostics")

    def on_show_dashboard_dns_clicked(self, _button) -> None:
        if int(getattr(self, "dashboard_dns_server_count", 0) or 0) <= 1:
            return
        self.dashboard_dns_expanded = not bool(getattr(self, "dashboard_dns_expanded", False))
        self.refresh_dashboard_interface_metric()
        dns_text = getattr(self, "dashboard_dns_full_text", "—")
        message = "DNS раскрыт полностью." if self.dashboard_dns_expanded else "DNS снова свёрнут."
        self.set_status(message)
        self.append_log("window", f"{message} {dns_text}")

    def on_dashboard_primary_action_clicked(self, _button) -> None:
        action_id = getattr(self, "dashboard_primary_action_id", None)
        if action_id == "open-subscriptions":
            self.show_page("subscriptions")
            return
        if action_id == "open-diagnostics":
            self.show_page("log")
            return
        if action_id in {"start-runtime", "stop-runtime", "takeover-runtime", "cleanup-artifacts", "capture-diagnostics"}:
            self.trigger_action(action_id, source="window")

    def connection_target_label(self, payload: dict[str, Any]) -> tuple[str, str]:
        active_node = payload.get("active_node", {}) or {}
        connection = payload.get("connection", {}) or {}
        node_name = self.node_display_name(active_node.get("name") or connection.get("active_name"), fallback="")
        protocol = str(connection.get("protocol_label") or active_node.get("protocol") or "").strip().upper()

        if node_name and protocol and protocol != "—":
            return node_name, f"{node_name} · {protocol}"
        if node_name:
            return node_name, node_name
        if protocol and protocol != "—":
            return protocol, protocol
        return "", "узел не выбран"

    def user_facing_config_origin_label(self, value: object) -> str:
        candidate = str(value or "").strip().lower()
        if candidate == "generated":
            return "Сгенерированный конфиг"
        if candidate == "snapshot":
            return "Снимок активного подключения"
        if candidate:
            return str(value)
        return "—"

    def dashboard_primary_action_spec(self) -> dict[str, Any]:
        payload = getattr(self, "last_status_payload", None) or {}
        runtime = payload.get("runtime", {}) or {}
        summary = payload.get("summary", {}) or {}
        processes = payload.get("processes", {}) or {}
        node_name, node_label = self.connection_target_label(payload)
        summary_state = str(summary.get("state") or "stopped")
        is_busy = getattr(self, "action_in_flight", None) is not None
        ownership = str(runtime.get("ownership") or "")
        stop_allowed = bool(runtime.get("stop_allowed", True))
        can_disconnect = (
            not bool(runtime.get("start_blocked"))
            and stop_allowed
            and (
                summary_state == "running"
                or bool(processes.get("xray_alive"))
                or bool(processes.get("tun_present"))
            )
        )

        if is_busy:
            return {
                "action_id": None,
                "button_label": "Выполняется…",
                "summary": "Дождитесь завершения текущего действия.",
                "hint": f"Сейчас выполняется: {self.action_label(self.action_in_flight or '')}.",
                "variant": "secondary",
                "enabled": False,
                "tooltip": f"Выполняется: {self.action_label(self.action_in_flight or '')}.",
            }

        if can_disconnect:
            return {
                "action_id": "stop-runtime",
                "button_label": "Отключиться",
                "summary": f"Сейчас подключено через узел: {node_label}.",
                "hint": "",
                "variant": "danger",
                "enabled": True,
                "tooltip": "Остановить текущее подключение и восстановить DNS.",
            }

        if runtime.get("start_blocked"):
            return {
                "action_id": None,
                "button_label": "Подключиться",
                "summary": f"Выбран узел: {node_label}." if node_name else "Подключение временно недоступно.",
                "hint": "" if ownership == "foreign" else "Источник подключения пока не подтверждён.",
                "variant": "secondary",
                "enabled": False,
                "tooltip": self.concise_runtime_block_message(runtime, for_action_hint=True),
            }

        if runtime.get("routing_enabled") and not runtime.get("routing_ready"):
            routing_error = str(runtime.get("routing_error") or "Маршрутизация ещё не готова.")
            return {
                "action_id": None,
                "button_label": "Подключиться",
                "summary": f"Выбран узел: {node_label}." if node_name else "Подключение временно недоступно.",
                "hint": "Сначала исправьте состояние маршрутизации.",
                "variant": "secondary",
                "enabled": False,
                "tooltip": routing_error,
            }

        if not node_name:
            return {
                "action_id": None,
                "button_label": "Подключиться",
                "summary": "Выберите узел ниже на этой вкладке.",
                "hint": "",
                "variant": "secondary",
                "enabled": False,
                "tooltip": "Сначала выберите узел в карточках ниже.",
            }

        if runtime.get("start_ready"):
            return {
                "action_id": "start-runtime",
                "button_label": "Подключиться",
                "summary": f"Готово к запуску через узел: {node_label}.",
                "hint": "",
                "variant": "primary",
                "enabled": True,
                "tooltip": str(runtime.get("next_start_reason") or "Запустить подключение через общий сервисный слой."),
            }

        next_reason = str(runtime.get("next_start_reason") or "Подключение пока не готово.")
        return {
            "action_id": None,
            "button_label": "Подключиться",
            "summary": f"Выбран узел: {node_label}.",
            "hint": "",
            "variant": "secondary",
            "enabled": False,
            "tooltip": next_reason,
        }

    def set_button_variant(self, button, variant: str) -> None:
        for current_variant in ("primary", "secondary", "danger"):
            remove_css_class(button, f"native-shell-button-{current_variant}")
        add_css_class(button, f"native-shell-button-{variant}")

    def update_dashboard_state_icon(self, summary: dict[str, Any], runtime: dict[str, Any]) -> None:
        label = getattr(self, "dashboard_labels", {}).get("hero_state_icon")
        if label is None:
            return
        for css_class in (
            "native-shell-status-dot-running",
            "native-shell-status-dot-warning",
            "native-shell-status-dot-stopped",
        ):
            remove_css_class(label, css_class)
        state = str(summary.get("state") or "stopped")
        if runtime.get("start_blocked") or state == "degraded":
            add_css_class(label, "native-shell-status-dot-warning")
        elif state == "running":
            add_css_class(label, "native-shell-status-dot-running")
        else:
            add_css_class(label, "native-shell-status-dot-stopped")

    def format_dns_summary(self, value: object) -> tuple[str, str, int]:
        raw = str(value or "").strip()
        servers = [item.strip() for item in raw.split(",") if item.strip()]
        if not servers:
            return "—", "—", 0
        full = ", ".join(servers)
        if len(servers) == 1:
            return full, full, 1
        return f"{servers[0]} + ещё {len(servers) - 1}", full, len(servers)

    def refresh_dashboard_interface_metric(self) -> None:
        tun_line = getattr(self, "dashboard_tun_line", "—")
        compact_dns = getattr(self, "dashboard_dns_compact_text", "—")
        full_dns = getattr(self, "dashboard_dns_full_text", "—")
        dns_value = full_dns if full_dns != "—" else compact_dns
        interface_text = self.dashboard_interface_text(tun_line, dns_value)
        self.set_metric_value("interface", interface_text)
        self.apply_dashboard_interface_markup(tun_line, dns_value)

        if self.dashboard_dns_button is None:
            return

        self.dashboard_dns_button.set_visible(False)
        self.dashboard_dns_button.set_sensitive(False)
        self.dashboard_dns_button.set_tooltip_text(full_dns)
        self.dashboard_dns_button.set_label("Показать все")

    def update_dashboard_conflict_bar(self, runtime: dict[str, Any]) -> None:
        if self.dashboard_conflict_bar is None or self.dashboard_conflict_label is None:
            return
        ownership = str(runtime.get("ownership") or "")
        state_root = str(runtime.get("state_bundle_project_root") or "—")
        visible = ownership == "foreign" and bool(runtime.get("stack_is_live"))
        self.dashboard_conflict_bar.set_visible(visible)
        self.dashboard_conflict_bar.set_revealed(visible)
        if not visible:
            return
        self.dashboard_conflict_label.set_label(
            f"Активное подключение уже запущено из другого bundle. Путь: {self.shorten_text(state_root, 84)}"
        )
        self.dashboard_conflict_label.set_tooltip_text(state_root)
        if self.dashboard_takeover_button is not None:
            self.dashboard_takeover_button.set_sensitive(True)

    def update_dashboard_from_status(self, payload: dict[str, Any]) -> None:
        summary = payload.get("summary", {}) or {}
        settings = payload.get("settings", {}) or {}
        processes = payload.get("processes", {}) or {}
        runtime = payload.get("runtime", {}) or {}
        connection = payload.get("connection", {}) or {}
        routing = payload.get("routing", {}) or {}
        traffic = payload.get("traffic", {}) or {}
        artifacts = payload.get("artifacts", {}) or {}
        last_action = payload.get("last_action", {}) or {}

        self.update_dashboard_state_icon(summary, runtime)
        current_connection = self.dashboard_connection_is_active(summary, runtime, processes)
        dashboard_state = self.user_facing_runtime_state_label(summary, runtime)
        if str(runtime.get("ownership") or "") == "foreign":
            dashboard_state = "Подключение недоступно"

        _node_name, node_label = self.connection_target_label(payload)
        subscription_label = self.active_subscription_display_name()
        title_label = node_label if current_connection and node_label != "узел не выбран" else dashboard_state
        subtitle_label = ""
        if not current_connection and node_label != "узел не выбран":
            subtitle_label = node_label

        shortened_title_label = self.shorten_text(title_label, 96)
        shortened_subtitle_label = self.shorten_text(subtitle_label, 96)
        self.set_dashboard_label("hero_state", shortened_title_label)
        self.set_dashboard_label("hero_active", shortened_subtitle_label)
        hero_active_widget = getattr(self, "dashboard_labels", {}).get("hero_active")
        if hero_active_widget is not None:
            hero_active_widget.set_visible(bool(subtitle_label))
            hero_active_widget.set_tooltip_text(subtitle_label if shortened_subtitle_label != subtitle_label else None)
        hero_state_widget = getattr(self, "dashboard_labels", {}).get("hero_state")
        if hero_state_widget is not None:
            hero_state_widget.set_tooltip_text(title_label if shortened_title_label != title_label else None)
        subscription_line = f"Подписка: {subscription_label}" if subscription_label else ""
        shortened_subscription_line = self.shorten_text(subscription_line, 96)
        self.set_dashboard_label("hero_subscription", shortened_subscription_line)
        hero_subscription_widget = getattr(self, "dashboard_labels", {}).get("hero_subscription")
        if hero_subscription_widget is not None:
            hero_subscription_widget.set_visible(bool(subscription_line))
            hero_subscription_widget.set_tooltip_text(subscription_line if shortened_subscription_line != subscription_line else None)
        tun_line = str(summary.get("tun_line") or connection.get("tun_interface") or "—")
        self.dashboard_tun_line = tun_line

        dns_summary, dns_full, dns_count = self.format_dns_summary(summary.get("dns_line") or connection.get("dns_servers") or "—")
        if dns_full != getattr(self, "dashboard_dns_full_text", "—"):
            self.dashboard_dns_expanded = False
        self.dashboard_dns_compact_text = dns_summary
        self.dashboard_dns_full_text = dns_full
        self.dashboard_dns_server_count = dns_count
        self.refresh_dashboard_interface_metric()

        self.refresh_dashboard_live_status_line()

        self.refresh_dashboard_badges(
            tun_interface=str(connection.get("tun_interface") or processes.get("tun_interface") or "tun0"),
            tun_present=bool(processes.get("tun_present")),
            file_logs_enabled=bool(settings.get("file_logs_enabled")),
            routing=routing,
        )
        self.update_dashboard_conflict_bar(runtime)

        last_action_message = str(last_action.get("message") or "Действий ещё не было.")
        if last_action.get("timestamp"):
            last_action_message = f"{last_action.get('timestamp')} · {last_action_message}"

        self.set_metric_value("uptime", self.format_connected_since(runtime.get("connected_since")))
        self.set_metric_value("rx", self.combine_rate_and_total(traffic.get("rx_rate_label"), traffic.get("rx_total_label")))
        self.set_metric_value("tx", self.combine_rate_and_total(traffic.get("tx_rate_label"), traffic.get("tx_total_label")))
        self.set_metric_value("tun", tun_line)
        self.set_metric_value("dns", dns_full)

        latest_diagnostic = str(artifacts.get("latest_diagnostic") or "Диагностические дампы ещё не снимались.")
        self.update_diagnostics_from_status(
            summary=summary,
            runtime=runtime,
            connection=connection,
            routing=routing,
            artifacts=artifacts,
            last_action=last_action,
            project_root=str(payload.get("project_root") or "—"),
            latest_diagnostic=latest_diagnostic,
        )

        if self.log_summary_label is not None:
            logs_payload = payload.get("logs", {}) or {}
            latest_error = logs_payload.get("latest_error") or {}
            if latest_error:
                self.log_summary_label.set_label(f"Последняя ошибка: {latest_error.get('message')}")
            else:
                self.log_summary_label.set_label(last_action_message)

        self.refresh_dashboard_controls()

    def update_diagnostics_from_status(
        self,
        *,
        summary: dict[str, Any],
        runtime: dict[str, Any],
        connection: dict[str, Any],
        routing: dict[str, Any],
        artifacts: dict[str, Any],
        last_action: dict[str, Any],
        project_root: str,
        latest_diagnostic: str,
    ) -> None:
        state_root = str(runtime.get("state_bundle_project_root") or "—")
        ownership = str(runtime.get("ownership") or "")

        diagnostic_status = self.user_facing_runtime_state_label(summary, runtime)
        if runtime.get("start_blocked"):
            diagnostic_status = (
                f"{diagnostic_status}\n"
                f"{self.concise_runtime_block_message(runtime, for_action_hint=True)}\n"
                f"Путь активного экземпляра: {state_root}"
            )
        else:
            diagnostic_status = f"{diagnostic_status}\n{str(summary.get('description') or 'Подключение работает в штатном режиме.')}"
        self.set_diagnostic_label("diagnostic_status", diagnostic_status)
        if self.diagnostic_takeover_button is not None:
            self.diagnostic_takeover_button.set_sensitive(ownership == "foreign" and bool(runtime.get("stack_is_live")))

        if ownership == "foreign" and bool(runtime.get("stack_is_live")):
            diagnostic_instance = (
                "Активный экземпляр: другой Subvost\n"
                f"Где он запущен: {state_root}\n"
                f"Текущий проект: {project_root}"
            )
        elif ownership == "foreign":
            diagnostic_instance = (
                "Старый state-файл: другой Subvost\n"
                f"Где он был запущен: {state_root}\n"
                f"Текущий проект: {project_root}"
            )
        elif ownership == "current":
            diagnostic_instance = (
                "Активный экземпляр: этот Subvost\n"
                f"Проект: {project_root}"
            )
        else:
            diagnostic_instance = (
                "Активный экземпляр: источник не подтверждён\n"
                f"Текущий проект: {project_root}"
            )
        self.set_diagnostic_label("diagnostic_instance", diagnostic_instance)

        transport = " · ".join(
            part for part in [connection.get("protocol_label"), connection.get("transport_label"), connection.get("security_label")] if part
        ) or "—"
        remote_endpoint = str(connection.get("remote_endpoint") or "—")
        remote_sni = str(connection.get("remote_sni") or "—")
        tun_label = str(summary.get("tun_line") or connection.get("tun_interface") or "—")
        dns_label = str(connection.get("dns_servers") or summary.get("dns_line") or "—")
        routing_text = "Маршрутизация отключена"
        if routing.get("enabled") and routing.get("runtime_ready"):
            routing_text = f"Маршрутизация: {routing.get('active_profile', {}).get('name') or 'активна'}"
        elif routing.get("enabled"):
            routing_text = f"Маршрутизация: ошибка ({routing.get('runtime_error') or 'служебный режим не готов'})"
        self.set_diagnostic_label(
            "diagnostic_connection",
            (
                f"Протокол: {transport}\n"
                f"Адрес: {remote_endpoint}\n"
                f"SNI: {remote_sni}\n"
                f"TUN: {tun_label}\n"
                f"DNS: {dns_label}\n"
                f"{routing_text}"
            ),
        )

        config_origin = self.user_facing_config_origin_label(runtime.get("config_origin"))
        config_value = runtime.get("active_xray_config") or artifacts.get("generated_xray_config") or "—"
        runtime_state_status = artifacts.get("runtime_state_status", {}) or {}
        backup_status = artifacts.get("resolv_backup_status", {}) or {}
        dumps_status = artifacts.get("diagnostic_dumps", {}) or {}
        cleanup_label = "доступна" if artifacts.get("cleanup_available") else "не требуется"
        if not artifacts.get("cleanup_available") and runtime_state_status.get("status") == "active_current":
            cleanup_label = "не требуется: state текущего подключения сохраняется"
        if artifacts.get("manual_attention_required"):
            cleanup_label = f"требуется ручной контроль ({artifacts.get('manual_reason') or 'причина не указана'})"
        self.set_diagnostic_label(
            "diagnostic_files",
            (
                f"Конфиг ({config_origin}): {config_value}\n"
                f"State-файл: {artifacts.get('state_file') or '—'}\n"
                f"Статус state: {runtime_state_status.get('label') or '—'}\n"
                f"DNS backup: {'есть' if backup_status.get('exists') else 'нет'}\n"
                f"Диагностические дампы: {dumps_status.get('total_count', 0)} всего, "
                f"{dumps_status.get('expired_count', 0)} старше retention\n"
                f"Очистка: {cleanup_label}\n"
                f"Последний дамп: {latest_diagnostic}"
            ),
        )

        last_action_message = str(last_action.get("message") or "Действий ещё не было.")
        if last_action.get("timestamp"):
            last_action_message = f"{last_action.get('timestamp')}\n{last_action_message}"
        self.set_diagnostic_label("diagnostic_last_action", last_action_message)

    def set_dashboard_label(self, key: str, value: str) -> None:
        label = getattr(self, "dashboard_labels", {}).get(key)
        if label is None:
            return
        label.set_label(value)

    def set_diagnostic_label(self, key: str, value: str) -> None:
        label = getattr(self, "diagnostic_labels", {}).get(key)
        if label is None:
            return
        label.set_label(value)

    def set_diagnostic_action_feedback(self, state: str, message: str) -> None:
        label = getattr(self, "diagnostic_action_label", None)
        if label is None:
            return
        for css_class in (
            "native-shell-action-feedback-busy",
            "native-shell-action-feedback-success",
            "native-shell-action-feedback-error",
        ):
            remove_css_class(label, css_class)
        if state in {"busy", "success", "error"}:
            add_css_class(label, f"native-shell-action-feedback-{state}")
        label.set_label(message)

    def set_settings_update_feedback(self, state: str, message: str) -> None:
        label = getattr(self, "settings_update_feedback_label", None)
        if label is None:
            return
        for css_class in (
            "native-shell-action-feedback-busy",
            "native-shell-action-feedback-success",
            "native-shell-action-feedback-error",
        ):
            remove_css_class(label, css_class)
        if state in {"busy", "success", "error"}:
            add_css_class(label, f"native-shell-action-feedback-{state}")
        label.set_label(message)

    def refresh_settings_controls(self) -> None:
        button = getattr(self, "settings_update_button", None)
        if button is None:
            return
        is_busy = getattr(self, "action_in_flight", None) is not None
        button.set_sensitive(not is_busy)
        if is_busy:
            button.set_tooltip_text(f"Сейчас выполняется: {self.action_label(self.action_in_flight or '')}.")
        else:
            button.set_tooltip_text("Запустить обновление ядра Xray через pkexec.")

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

    def refresh_dashboard_badges(
        self,
        *,
        tun_interface: str,
        tun_present: bool,
        file_logs_enabled: bool,
        routing: dict[str, Any],
    ) -> None:
        if self.dashboard_badge_box is None:
            return
        child = self.dashboard_badge_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.dashboard_badge_box.remove(child)
            child = next_child

        routing_enabled = bool(routing.get("enabled") and routing.get("runtime_ready"))
        routing_profile = routing.get("active_profile", {}) or {}
        routing_name = str(routing_profile.get("name") or "").strip()
        routing_label = f"Маршрут {routing_name}" if routing_enabled and routing_name else "Маршрут активен"
        routing_tone = "success"
        routing_icon = "emblem-ok-symbolic"
        if not routing_enabled:
            routing_label = f"Маршрут {routing_name}" if routing_name else "Маршрут не активен"
            routing_tone = "danger" if routing.get("enabled") else "warning"
            routing_icon = "window-close-symbolic" if routing.get("enabled") else "dialog-warning-symbolic"

        badge_specs = (
            (
                f"{tun_interface} найден" if tun_present else f"{tun_interface} не найден",
                "success" if tun_present else "danger",
                "emblem-ok-symbolic" if tun_present else "window-close-symbolic",
            ),
            (
                "Логирование включено" if file_logs_enabled else "Логирование выключено",
                "success" if file_logs_enabled else "warning",
                "emblem-ok-symbolic" if file_logs_enabled else "dialog-warning-symbolic",
            ),
            (routing_label, routing_tone, routing_icon),
        )
        for label, tone, icon_name in badge_specs:
            self.dashboard_badge_box.append(self.make_status_badge(label, tone, icon_name))

    def refresh_dashboard_controls(self) -> None:
        is_busy = getattr(self, "action_in_flight", None) is not None

        action_buttons = getattr(self, "dashboard_action_buttons", {})
        primary_button = action_buttons.get("primary-connect")
        open_nodes_button = action_buttons.get("open-subscriptions")
        diag_button = action_buttons.get("capture-diagnostics")
        cleanup_button = action_buttons.get("cleanup-artifacts")
        open_diag_button = action_buttons.get("open-diagnostics")

        spec = self.dashboard_primary_action_spec()
        self.dashboard_primary_action_id = spec["action_id"]

        if primary_button is not None:
            primary_button.set_label(str(spec["button_label"]))
            primary_button.set_sensitive(bool(spec["enabled"]))
            primary_button.set_tooltip_text(str(spec["tooltip"]))
            self.set_button_variant(primary_button, str(spec["variant"]))
            if hasattr(primary_button, "set_visible"):
                primary_button.set_visible(True)

        if open_nodes_button is not None:
            open_nodes_button.set_label("Узлы")
            open_nodes_button.set_sensitive(True)
            if hasattr(open_nodes_button, "set_visible"):
                open_nodes_button.set_visible(True)

        if diag_button is not None:
            diag_button.set_sensitive(not is_busy)
            diag_button.set_tooltip_text("Снять диагностический дамп текущего подключения.")

        if cleanup_button is not None:
            cleanup_button.set_sensitive(not is_busy)
            cleanup_button.set_tooltip_text("Очистить stale state, orphan DNS backup и старые служебные дампы.")

        if open_diag_button is not None:
            open_diag_button.set_label("Диагностика")
            open_diag_button.set_sensitive(True)
            if hasattr(open_diag_button, "set_visible"):
                open_diag_button.set_visible(True)

        self.set_dashboard_label("action_summary", str(spec["summary"]))
        self.set_dashboard_label("action_hint", str(spec["hint"]))

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
            self.set_status("Трей недоступен: окно нельзя безопасно скрыть.")
            self.append_log(reason, "Скрытие окна пропущено: трей недоступен.")
            return
        self.window.set_visible(False)
        self.set_status("Окно скрыто, приложение остаётся доступным через трей.")
        self.append_log(reason, "Главное окно скрыто и оставлено работать в фоне.")

    def open_settings_window(self) -> None:
        if self.settings_window is None:
            self.settings_window = self.build_settings_window()
        self.refresh_settings_controls()
        self.settings_window.present()
        self.append_log("settings", "Открыто окно настроек интерфейса.")

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
            self.append_log("settings", f"Настройка закрытия в трей изменена: {int(value)}.")
        elif key == "start_minimized_to_tray":
            self.append_log("settings", f"Настройка старта в трее изменена: {int(value)}.")
        elif key == "file_logs_enabled":
            self.append_log("settings", f"Настройка файловых логов изменена: {int(value)}.")
        self.refresh_status_after_settings_change()

    def refresh_status_after_settings_change(self) -> None:
        if self.tray_support.available:
            self.set_status(
                "Настройки интерфейса сохранены. "
                f"Закрытие в трей: {'вкл' if self.settings.close_to_tray else 'выкл'}, "
                f"старт в трее: {'вкл' if self.settings.start_minimized_to_tray else 'выкл'}."
            )
        else:
            self.set_status(f"Настройки интерфейса сохранены. Трей недоступен: {self.tray_support.reason}")
        self.request_status_refresh(reason="settings-change", silent=True)

    def persist_settings(self) -> None:
        self.runtime_service.save_settings(
            self.settings.file_logs_enabled,
            close_to_tray=self.settings.close_to_tray,
            start_minimized_to_tray=self.settings.start_minimized_to_tray,
            theme=self.settings.theme,
            artifact_retention_days=self.settings.artifact_retention_days,
        )

    def apply_theme_preference(self, theme: str) -> None:
        settings = self.Gtk.Settings.get_default()
        if settings is None:
            return
        try:
            settings.set_property(
                "gtk-application-prefer-dark-theme",
                normalize_native_shell_theme(theme) == "dark",
            )
        except (TypeError, ValueError):
            return

    def append_log(self, source: str, message: str) -> None:
        now = datetime.now()
        entry = {
            "timestamp": now.isoformat(timespec="seconds"),
            "name": source,
            "level": log_level_from_text(message),
            "message": message,
            "details": "",
            "source": "shell",
        }
        self.shell_log_entries.append(entry)
        self.shell_log_entries = self.shell_log_entries[-200:]
        line = f"[{now.strftime('%H:%M:%S')}] [{source}] {message}"
        self.log_lines.append(line)
        self.log_lines = self.log_lines[-200:]
        if self.settings.file_logs_enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        self.refresh_log_view()

    def refresh_log_view(self) -> None:
        normalized_filter = normalize_native_shell_log_filter(getattr(self, "log_filter", "all"))
        self.log_filter = normalized_filter
        shell_entries, bundle_entries = self.visible_log_entries()
        all_entries = self.current_shell_log_entries() + self.current_bundle_log_entries()
        latest_error = latest_error_from_log_entries(all_entries)
        last_action = (getattr(self, "last_status_payload", None) or {}).get("last_action", {}) or {}

        if self.log_buffer is not None:
            self.log_buffer.set_text(self.visible_log_text())

        if self.log_summary_label is not None:
            if latest_error:
                source_label = native_shell_log_source_label(latest_error.get("source"))
                level_label = native_shell_log_level_label(latest_error.get("level"))
                self.log_summary_label.set_label(
                    f"Последняя ошибка: {level_label} · {source_label} · {latest_error.get('message')}"
                )
            elif last_action.get("message"):
                self.log_summary_label.set_label(f"Последнее действие: {last_action.get('message')}")
            else:
                self.log_summary_label.set_label("Ошибок пока нет. Последних действий тоже нет.")

        if self.log_meta_label is not None:
            self.log_meta_label.set_label(
                "Фильтр: "
                f"{native_shell_log_filter_label(normalized_filter)}. "
                f"Оболочка интерфейса: {len(shell_entries)}. "
                f"Журнал подключения: {len(bundle_entries)}."
            )

        if self.log_export_label is not None:
            export_path = self.last_log_export_path or self.resolve_log_export_dir()
            self.log_export_label.set_label(f"Экспорт: {export_path}")

        for filter_id, button in getattr(self, "log_filter_buttons", {}).items():
            button.set_sensitive(filter_id != normalized_filter)

        has_entries = bool(shell_entries or bundle_entries)
        if self.log_copy_button is not None:
            self.log_copy_button.set_sensitive(has_entries)
        if self.log_export_button is not None:
            self.log_export_button.set_sensitive(has_entries)

    def set_status(self, message: str) -> None:
        if self.status_label is not None:
            self.status_label.set_label(message)

    def is_window_visible(self) -> bool:
        return bool(self.window is not None and self.window.get_visible())

    def start_tray_helper_if_needed(self) -> None:
        if not self.tray_support.available:
            self.append_log("tray", f"Трей-хелпер не запущен: {self.tray_support.reason}")
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
            APP_ICON_NAME,
        ]
        self.tray_process = subprocess.Popen(
            command,
            cwd=str(GUI_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.append_log("tray", f"Трей-хелпер запущен через {self.tray_support.backend_label}.")
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
            error=f"Трей-хелпер {('завершился' if stage == 'startup' else 'остановился')} с кодом {return_code}.",
        )
        self.tray_process = None
        self.append_log("tray", self.tray_support.reason)
        self.set_dashboard_label("tray_note", f"Трей: {self.tray_support.reason}")
        if self.window is not None and not self.window.get_visible():
            self.window.present()
            self.set_status(
                "Трей недоступен. Главное окно автоматически показано, чтобы приложение не осталось скрытым."
            )
            self.append_log("tray", "Главное окно автоматически показано после деградации трея.")
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
        self.append_log(source, "Приложение завершает работу по команде интерфейса или трея.")
        self.app.quit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GTK4-прототип нативного интерфейса для Subvost Xray TUN.")
    parser.add_argument(
        "--disable-tray",
        action="store_true",
        help="Принудительно отключить трей и проверить fallback-поведение.",
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
