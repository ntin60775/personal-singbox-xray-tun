#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


APP_ID = "io.subvost.XrayTunGui"
DEFAULT_TITLE = "Subvost Xray TUN"
DEFAULT_WIDTH = 1440
DEFAULT_HEIGHT = 960
STARTUP_HORIZONTAL_MARGIN = 28
STARTUP_VERTICAL_RESERVE = 56
MIN_WINDOW_WIDTH = 720
MIN_WINDOW_HEIGHT = 540
SOFTWARE_RENDERING_ENV_DEFAULTS = {
    "WEBKIT_DISABLE_DMABUF_RENDERER": "1",
    "WEBKIT_DMABUF_RENDERER_FORCE_SHM": "1",
    "WEBKIT_WEBGL_DISABLE_GBM": "1",
    "WEBKIT_SKIA_ENABLE_CPU_RENDERING": "1",
}


@dataclass(frozen=True)
class RuntimeCandidate:
    gtk_namespace: str
    gtk_version: str
    gtk_module: str
    webkit_namespace: str
    webkit_version: str
    webkit_module: str
    label: str


RUNTIME_CANDIDATES = (
    RuntimeCandidate("Gtk", "4.0", "Gtk", "WebKit", "6.0", "WebKit", "Gtk4 + WebKitGTK 6.0"),
    RuntimeCandidate("Gtk", "3.0", "Gtk", "WebKit2", "4.1", "WebKit2", "Gtk3 + WebKitGTK 4.1"),
    RuntimeCandidate("Gtk", "3.0", "Gtk", "WebKit2", "4.0", "WebKit2", "Gtk3 + WebKitGTK 4.0"),
)


class WebViewUnavailableError(RuntimeError):
    pass


def apply_software_rendering_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if environ is None else environ
    for key, value in SOFTWARE_RENDERING_ENV_DEFAULTS.items():
        env.setdefault(key, value)
    return env


def has_graphical_session(environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


def ensure_graphical_session(environ: dict[str, str] | None = None) -> None:
    if not has_graphical_session(environ):
        raise WebViewUnavailableError("Нет графической сессии: ожидается DISPLAY или WAYLAND_DISPLAY.")


def available_namespace_versions() -> dict[str, set[str]]:
    try:
        import gi
    except ImportError as exc:
        raise WebViewUnavailableError(f"Не найден python3-gi: {exc}") from exc

    gi.require_version("GIRepository", "2.0")
    repository_module = importlib.import_module("gi.repository.GIRepository")
    repository = repository_module.Repository.get_default()
    namespaces = {candidate.gtk_namespace for candidate in RUNTIME_CANDIDATES}
    namespaces.update(candidate.webkit_namespace for candidate in RUNTIME_CANDIDATES)
    versions: dict[str, set[str]] = {}

    for namespace in namespaces:
        versions[namespace] = set(repository.enumerate_versions(namespace))

    return versions


def select_runtime(
    require_version: Callable[[str, str], None],
    versions_by_namespace: dict[str, set[str]] | None = None,
) -> RuntimeCandidate:
    errors: list[str] = []

    for candidate in RUNTIME_CANDIDATES:
        if versions_by_namespace is not None:
            gtk_versions = versions_by_namespace.get(candidate.gtk_namespace, set())
            webkit_versions = versions_by_namespace.get(candidate.webkit_namespace, set())
            if candidate.gtk_version not in gtk_versions or candidate.webkit_version not in webkit_versions:
                errors.append(
                    f"{candidate.label}: недоступны версии {candidate.gtk_namespace} {candidate.gtk_version}"
                    f" / {candidate.webkit_namespace} {candidate.webkit_version}"
                )
                continue

        try:
            require_version(candidate.gtk_namespace, candidate.gtk_version)
            require_version(candidate.webkit_namespace, candidate.webkit_version)
        except (ImportError, ValueError) as exc:
            errors.append(f"{candidate.label}: {exc}")
            continue
        return candidate

    details = "; ".join(errors) if errors else "Не найден совместимый runtime для GTK/WebKitGTK."
    raise WebViewUnavailableError(details)


def resolve_runtime_candidate(environ: dict[str, str] | None = None) -> RuntimeCandidate:
    ensure_graphical_session(environ)
    try:
        import gi
    except ImportError as exc:
        raise WebViewUnavailableError(f"Не найден python3-gi: {exc}") from exc

    return select_runtime(gi.require_version, versions_by_namespace=available_namespace_versions())


def load_runtime_modules(candidate: RuntimeCandidate):
    gtk = importlib.import_module(f"gi.repository.{candidate.gtk_module}")
    gio = importlib.import_module("gi.repository.Gio")
    glib = importlib.import_module("gi.repository.GLib")
    gdk = importlib.import_module("gi.repository.Gdk")
    webkit = importlib.import_module(f"gi.repository.{candidate.webkit_module}")
    return gtk, gio, glib, gdk, webkit


def compute_startup_window_size(
    requested_width: int,
    requested_height: int,
    monitor_width: int,
    monitor_height: int,
    *,
    horizontal_margin: int = STARTUP_HORIZONTAL_MARGIN,
    vertical_reserve: int = STARTUP_VERTICAL_RESERVE,
) -> tuple[int, int]:
    usable_width = max(MIN_WINDOW_WIDTH, int(monitor_width) - max(0, horizontal_margin) * 2)
    usable_height = max(MIN_WINDOW_HEIGHT, int(monitor_height) - max(0, vertical_reserve))
    requested_width = max(MIN_WINDOW_WIDTH, int(requested_width))
    requested_height = max(MIN_WINDOW_HEIGHT, int(requested_height))
    target_width = min(requested_width, usable_width)
    target_height = min(max(requested_height, usable_height), usable_height)
    return target_width, target_height


def build_software_rendering_settings(webkit_module) -> dict[str, object]:
    settings: dict[str, object] = {
        "enable-webgl": False,
        "enable-2d-canvas-acceleration": False,
    }
    policy = getattr(getattr(webkit_module, "HardwareAccelerationPolicy", None), "NEVER", None)
    if policy is not None:
        settings["hardware-acceleration-policy"] = policy
    return settings


def apply_webview_software_rendering_settings(webview, webkit_module) -> dict[str, object]:
    settings = webview.get_settings()
    if settings is None:
        return {}

    applied: dict[str, object] = {}
    for name, value in build_software_rendering_settings(webkit_module).items():
        try:
            settings.set_property(name, value)
        except (AttributeError, TypeError, ValueError):
            continue
        applied[name] = value
    return applied


class EmbeddedWebViewApp:
    def __init__(self, candidate: RuntimeCandidate, args: argparse.Namespace) -> None:
        self.candidate = candidate
        self.args = args
        self.Gtk, self.Gio, self.GLib, self.Gdk, self.WebKit = load_runtime_modules(candidate)
        self.GLib.set_prgname("subvost-xray-tun")
        self.GLib.set_application_name(args.title)
        self.app = self.Gtk.Application(application_id=APP_ID, flags=self.Gio.ApplicationFlags.FLAGS_NONE)
        self.app.connect("activate", self.on_activate)
        self.window = None
        self.webview = None

    def run(self) -> int:
        return int(self.app.run([]))

    def on_activate(self, app) -> None:
        if self.window is None:
            self.window = self.build_window(app)
            self.webview = self.build_webview()
            self.attach_webview()
            self.connect_close_handler()
            self.webview.load_uri(self.args.url)
        self.window.present()

    def build_window(self, app):
        window = self.Gtk.ApplicationWindow(application=app)
        window.set_title(self.args.title)
        width, height = self.resolve_startup_window_size()
        window.set_default_size(width, height)
        self.apply_icon(window)
        return window

    def build_webview(self):
        webview = self.WebKit.WebView()
        apply_webview_software_rendering_settings(webview, self.WebKit)
        webview.connect("notify::title", self.on_title_changed)
        return webview

    def attach_webview(self) -> None:
        if self.candidate.gtk_version.startswith("4."):
            self.window.set_child(self.webview)
            return

        self.window.add(self.webview)
        self.window.show_all()

    def connect_close_handler(self) -> None:
        if self.candidate.gtk_version.startswith("4."):
            self.window.connect("close-request", self.on_close_request)
            return

        self.window.connect("delete-event", self.on_delete_event)

    def on_close_request(self, *_args):
        self.app.quit()
        return False

    def on_delete_event(self, *_args):
        self.app.quit()
        return False

    def on_title_changed(self, webview, *_args) -> None:
        page_title = webview.get_title()
        if page_title:
            self.window.set_title(page_title)

    def apply_icon(self, window) -> None:
        if not self.args.icon_path:
            return

        icon_path = Path(self.args.icon_path)
        if not icon_path.is_file():
            return

        if self.candidate.gtk_version.startswith("4."):
            return

        try:
            window.set_icon_from_file(str(icon_path))
        except Exception:
            return

    def resolve_startup_window_size(self) -> tuple[int, int]:
        monitor_size = self.resolve_monitor_size()
        if monitor_size is None:
            return self.args.width, self.args.height

        monitor_width, monitor_height = monitor_size
        return compute_startup_window_size(
            self.args.width,
            self.args.height,
            monitor_width,
            monitor_height,
        )

    def resolve_monitor_size(self) -> tuple[int, int] | None:
        display = self.Gdk.Display.get_default()
        if display is None:
            return None

        geometry = self.resolve_monitor_geometry(display)
        if geometry is None:
            return None

        width = int(getattr(geometry, "width", 0) or 0)
        height = int(getattr(geometry, "height", 0) or 0)
        if width <= 0 or height <= 0:
            return None
        return width, height

    def resolve_monitor_geometry(self, display):
        if self.candidate.gtk_version.startswith("4."):
            monitors = display.get_monitors()
            if monitors is None or monitors.get_n_items() == 0:
                return None
            monitor = monitors.get_item(0)
            if monitor is None or not hasattr(monitor, "get_geometry"):
                return None
            return monitor.get_geometry()

        monitor = None
        if hasattr(display, "get_primary_monitor"):
            monitor = display.get_primary_monitor()
        if monitor is None and hasattr(display, "get_monitor"):
            try:
                monitor = display.get_monitor(0)
            except Exception:
                monitor = None
        if monitor is None:
            return None
        if hasattr(monitor, "get_workarea"):
            return monitor.get_workarea()
        if hasattr(monitor, "get_geometry"):
            return monitor.get_geometry()
        return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Встроенное GTK/WebKitGTK окно для локального GUI Subvost.")
    parser.add_argument("--url", default="http://127.0.0.1:8421", help="URL локального GUI backend-а.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Заголовок окна.")
    parser.add_argument("--icon-path", default="", help="Абсолютный путь к SVG/PNG-иконке, если доступен.")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Ширина окна по умолчанию.")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Высота окна по умолчанию.")
    parser.add_argument("--check", action="store_true", help="Проверить доступность встроенного webview без запуска окна.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    apply_software_rendering_environment()

    try:
        candidate = resolve_runtime_candidate()
    except WebViewUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        print(candidate.label)
        return 0

    app = EmbeddedWebViewApp(candidate, args)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
