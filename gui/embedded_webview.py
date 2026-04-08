#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


APP_ID = "io.subvost.XrayTunGui"
DEFAULT_TITLE = "Subvost Xray TUN"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 960
STARTUP_HORIZONTAL_MARGIN = 28
STARTUP_VERTICAL_RESERVE = 56
MIN_WINDOW_WIDTH = 720
MIN_WINDOW_HEIGHT = 540
SOFTWARE_RENDERING_ENV_DEFAULTS = {
    "WEBKIT_DISABLE_COMPOSITING_MODE": "1",
    "WEBKIT_DISABLE_DMABUF_RENDERER": "1",
    "WEBKIT_DMABUF_RENDERER_FORCE_SHM": "1",
    "WEBKIT_WEBGL_DISABLE_GBM": "1",
    "WEBKIT_SKIA_ENABLE_CPU_RENDERING": "1",
}
WEBVIEW_BACKGROUND_RGBA = (9 / 255, 16 / 255, 25 / 255, 1.0)
EMBEDDED_SURFACE_HEX = "#091019"
WINDOW_BACKGROUND_CSS_CLASS = "subvost-embedded-window"
ROOT_CONTAINER_CSS_CLASS = "subvost-embedded-root"
APP_TERMINATE_ROUTE = "/api/app/terminate"
APP_TERMINATE_TIMEOUT_SECS = 180.0


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


def build_webview_background_rgba(gdk_module, rgba: tuple[float, float, float, float] = WEBVIEW_BACKGROUND_RGBA):
    rgba_class = getattr(gdk_module, "RGBA", None)
    if rgba_class is None:
        return None
    color = rgba_class()
    color.red, color.green, color.blue, color.alpha = rgba
    return color


def apply_webview_background_color(webview, gdk_module) -> bool:
    if not hasattr(webview, "set_background_color"):
        return False

    color = build_webview_background_rgba(gdk_module)
    if color is None:
        return False

    try:
        webview.set_background_color(color)
    except Exception:
        return False
    return True


def add_css_class(widget, css_class: str) -> bool:
    get_style_context = getattr(widget, "get_style_context", None)
    if get_style_context is None:
        return False

    style_context = get_style_context()
    add_class = getattr(style_context, "add_class", None)
    if add_class is None:
        return False

    add_class(css_class)
    return True


def build_embedded_window_css(background_hex: str = EMBEDDED_SURFACE_HEX) -> bytes:
    return f"""
window.{WINDOW_BACKGROUND_CSS_CLASS},
window.{WINDOW_BACKGROUND_CSS_CLASS} > widget,
window.{WINDOW_BACKGROUND_CSS_CLASS} box,
box.{ROOT_CONTAINER_CSS_CLASS},
box.{ROOT_CONTAINER_CSS_CLASS} > widget,
box.{ROOT_CONTAINER_CSS_CLASS} scrolledwindow,
box.{ROOT_CONTAINER_CSS_CLASS} viewport,
box.{ROOT_CONTAINER_CSS_CLASS} webview {{
  background: {background_hex};
  background-color: {background_hex};
}}
""".encode("utf-8")


def build_css_provider(gtk_module, css_data: bytes):
    css_provider_class = getattr(gtk_module, "CssProvider", None)
    if css_provider_class is None:
        return None

    provider = css_provider_class()
    load_from_data = getattr(provider, "load_from_data", None)
    if load_from_data is None:
        return None

    try:
        load_from_data(css_data)
    except TypeError:
        load_from_data(css_data.decode("utf-8"))
    except Exception:
        return None
    return provider


def apply_window_background_css(window, gtk_module, gdk_module):
    add_css_class(window, WINDOW_BACKGROUND_CSS_CLASS)
    provider = build_css_provider(gtk_module, build_embedded_window_css())
    if provider is None:
        return None

    priority = getattr(gtk_module, "STYLE_PROVIDER_PRIORITY_APPLICATION", 600)
    style_context_class = getattr(gtk_module, "StyleContext", None)
    if style_context_class is None:
        return None

    add_provider_for_display = getattr(style_context_class, "add_provider_for_display", None)
    if callable(add_provider_for_display):
        display_class = getattr(gdk_module, "Display", None)
        display = display_class.get_default() if display_class is not None and hasattr(display_class, "get_default") else None
        if display is not None:
            add_provider_for_display(display, provider, priority)
            return provider

    add_provider_for_screen = getattr(style_context_class, "add_provider_for_screen", None)
    if callable(add_provider_for_screen):
        screen_class = getattr(gdk_module, "Screen", None)
        screen = screen_class.get_default() if screen_class is not None and hasattr(screen_class, "get_default") else None
        if screen is not None:
            add_provider_for_screen(screen, provider, priority)
            return provider

    return None


def build_webview_container(gtk_module):
    orientation = getattr(getattr(gtk_module, "Orientation", None), "VERTICAL", 1)
    container = gtk_module.Box(orientation=orientation)
    if hasattr(container, "set_hexpand"):
        container.set_hexpand(True)
    if hasattr(container, "set_vexpand"):
        container.set_vexpand(True)
    add_css_class(container, ROOT_CONTAINER_CSS_CLASS)
    return container


def build_app_terminate_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}{APP_TERMINATE_ROUTE}"


def request_application_shutdown(
    base_url: str,
    *,
    source: str = "window-close",
    timeout: float = APP_TERMINATE_TIMEOUT_SECS,
    urlopen=urllib.request.urlopen,
) -> dict[str, object]:
    payload = json.dumps({"source": source}).encode("utf-8")
    request = urllib.request.Request(
        build_app_terminate_url(base_url),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        message = f"HTTP {exc.code}"
        try:
            error_payload = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            error_payload = {}
        if error_payload.get("message"):
            message = str(error_payload["message"])
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Не удалось связаться с GUI backend: {reason}") from exc

    try:
        response_payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception as exc:
        raise RuntimeError("GUI backend вернул некорректный ответ при завершении приложения.") from exc

    if not response_payload.get("ok"):
        raise RuntimeError(str(response_payload.get("message") or "GUI backend отклонил завершение приложения."))
    return response_payload


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
        self.container = None
        self.window_css_provider = None
        self.shutting_down = False

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
        self.window_css_provider = apply_window_background_css(window, self.Gtk, self.Gdk)
        return window

    def build_webview(self):
        webview = self.WebKit.WebView()
        apply_webview_software_rendering_settings(webview, self.WebKit)
        apply_webview_background_color(webview, self.Gdk)
        webview.connect("notify::title", self.on_title_changed)
        webview.connect("load-changed", self.on_load_changed)
        try:
            webview.connect("web-process-terminated", self.on_web_process_terminated)
        except TypeError:
            pass
        return webview

    def attach_webview(self) -> None:
        if self.container is None:
            self.container = build_webview_container(self.Gtk)

        if self.candidate.gtk_version.startswith("4."):
            self.container.append(self.webview)
            self.window.set_child(self.container)
            return

        self.container.pack_start(self.webview, True, True, 0)
        self.window.add(self.container)
        self.window.show_all()

    def connect_close_handler(self) -> None:
        if self.candidate.gtk_version.startswith("4."):
            self.window.connect("close-request", self.on_close_request)
            return

        self.window.connect("delete-event", self.on_delete_event)

    def on_close_request(self, *_args):
        return not self.close_application()

    def on_delete_event(self, *_args):
        return not self.close_application()

    def on_title_changed(self, webview, *_args) -> None:
        page_title = webview.get_title()
        if page_title:
            self.window.set_title(page_title)

    def on_load_changed(self, webview, *_args) -> None:
        apply_webview_background_color(webview, self.Gdk)

    def on_web_process_terminated(self, webview, *_args):
        apply_webview_background_color(webview, self.Gdk)
        print("Embedded WebKit web-process terminated.", file=sys.stderr, flush=True)
        return False

    def close_application(self) -> bool:
        if self.shutting_down:
            return True

        try:
            self.request_full_shutdown()
        except RuntimeError as exc:
            self.show_shutdown_error(str(exc))
            return False

        self.shutting_down = True
        self.app.quit()
        return True

    def request_full_shutdown(self) -> dict[str, object]:
        return request_application_shutdown(self.args.url, source="window-close")

    def show_shutdown_error(self, message: str) -> None:
        dialog_text = "Не удалось полностью закрыть приложение.\n" + (message or "Неизвестная ошибка.")

        try:
            dialog = self.Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=self.Gtk.MessageType.ERROR,
                buttons=self.Gtk.ButtonsType.CLOSE,
                text=dialog_text,
            )
        except TypeError:
            print(dialog_text, file=sys.stderr, flush=True)
            return

        if hasattr(dialog, "run"):
            dialog.run()
            dialog.destroy()
            return

        dialog.connect("response", lambda current_dialog, *_args: current_dialog.destroy())
        dialog.present()

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
