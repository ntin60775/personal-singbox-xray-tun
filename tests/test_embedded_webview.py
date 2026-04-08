from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import embedded_webview  # noqa: E402


class EmbeddedWebViewTests(unittest.TestCase):
    def test_build_app_terminate_url_appends_shutdown_route(self) -> None:
        self.assertEqual(
            embedded_webview.build_app_terminate_url("http://127.0.0.1:8421/"),
            "http://127.0.0.1:8421/api/app/terminate",
        )

    def test_build_app_gui_shutdown_url_appends_gui_only_shutdown_route(self) -> None:
        self.assertEqual(
            embedded_webview.build_app_gui_shutdown_url("http://127.0.0.1:8421/"),
            "http://127.0.0.1:8421/api/app/shutdown-gui",
        )

    def test_apply_software_rendering_environment_sets_defaults(self) -> None:
        env = {"DISPLAY": ":0", "WEBKIT_DISABLE_DMABUF_RENDERER": "0"}

        applied = embedded_webview.apply_software_rendering_environment(env)

        self.assertIs(applied, env)
        self.assertEqual(applied["WEBKIT_DISABLE_COMPOSITING_MODE"], "1")
        self.assertEqual(applied["WEBKIT_DISABLE_DMABUF_RENDERER"], "0")
        self.assertEqual(applied["WEBKIT_DMABUF_RENDERER_FORCE_SHM"], "1")
        self.assertEqual(applied["WEBKIT_WEBGL_DISABLE_GBM"], "1")
        self.assertEqual(applied["WEBKIT_SKIA_ENABLE_CPU_RENDERING"], "1")

    def test_has_graphical_session_accepts_display(self) -> None:
        self.assertTrue(embedded_webview.has_graphical_session({"DISPLAY": ":0"}))
        self.assertTrue(embedded_webview.has_graphical_session({"WAYLAND_DISPLAY": "wayland-0"}))
        self.assertFalse(embedded_webview.has_graphical_session({}))

    def test_ensure_graphical_session_raises_without_display(self) -> None:
        with self.assertRaises(embedded_webview.WebViewUnavailableError):
            embedded_webview.ensure_graphical_session({})

    def test_select_runtime_prefers_first_supported_candidate(self) -> None:
        seen: list[tuple[str, str]] = []

        def fake_require_version(namespace: str, version: str) -> None:
            seen.append((namespace, version))

        candidate = embedded_webview.select_runtime(
            fake_require_version,
            versions_by_namespace={"Gtk": {"4.0", "3.0"}, "WebKit": {"6.0"}, "WebKit2": {"4.1", "4.0"}},
        )
        self.assertEqual(candidate.label, "Gtk4 + WebKitGTK 6.0")
        self.assertEqual(seen[:2], [("Gtk", "4.0"), ("WebKit", "6.0")])

    def test_select_runtime_falls_back_to_gtk3_when_webkit6_is_missing(self) -> None:
        def fake_require_version(namespace: str, version: str) -> None:
            if (namespace, version) == ("Gtk", "4.0"):
                raise AssertionError("Gtk4 не должен require-иться без доступного WebKit 6.0")

        candidate = embedded_webview.select_runtime(
            fake_require_version,
            versions_by_namespace={"Gtk": {"4.0", "3.0"}, "WebKit": set(), "WebKit2": {"4.1"}},
        )
        self.assertEqual(candidate.label, "Gtk3 + WebKitGTK 4.1")

    def test_select_runtime_raises_when_all_candidates_fail(self) -> None:
        def fake_require_version(namespace: str, version: str) -> None:
            raise ValueError(f"missing {namespace} {version}")

        with self.assertRaises(embedded_webview.WebViewUnavailableError):
            embedded_webview.select_runtime(fake_require_version, versions_by_namespace={"Gtk": {"4.0", "3.0"}})

    def test_compute_startup_window_size_uses_full_available_height(self) -> None:
        width, height = embedded_webview.compute_startup_window_size(1280, 960, 1920, 1080)
        self.assertEqual(width, 1280)
        self.assertEqual(height, 1024)

    def test_compute_startup_window_size_caps_width_on_small_monitor(self) -> None:
        width, height = embedded_webview.compute_startup_window_size(1280, 960, 1280, 900)
        self.assertEqual(width, 1224)
        self.assertEqual(height, 844)

    def test_build_software_rendering_settings_prefers_never_acceleration(self) -> None:
        class Policy:
            NEVER = "never"

        class WebKitModule:
            HardwareAccelerationPolicy = Policy

        settings = embedded_webview.build_software_rendering_settings(WebKitModule)

        self.assertEqual(settings["hardware-acceleration-policy"], "never")
        self.assertFalse(settings["enable-webgl"])
        self.assertFalse(settings["enable-2d-canvas-acceleration"])

    def test_apply_webview_software_rendering_settings_skips_unsupported_properties(self) -> None:
        class FakeSettings:
            def __init__(self) -> None:
                self.values: dict[str, object] = {}

            def set_property(self, name: str, value: object) -> None:
                if name == "hardware-acceleration-policy":
                    raise TypeError("unsupported")
                self.values[name] = value

        class FakeWebView:
            def __init__(self) -> None:
                self.settings = FakeSettings()

            def get_settings(self) -> FakeSettings:
                return self.settings

        class Policy:
            NEVER = "never"

        class WebKitModule:
            HardwareAccelerationPolicy = Policy

        webview = FakeWebView()
        applied = embedded_webview.apply_webview_software_rendering_settings(webview, WebKitModule)

        self.assertEqual(
            applied,
            {
                "enable-webgl": False,
                "enable-2d-canvas-acceleration": False,
            },
        )
        self.assertEqual(
            webview.settings.values,
            {
                "enable-webgl": False,
                "enable-2d-canvas-acceleration": False,
            },
        )

    def test_build_webview_background_rgba_uses_project_dark_surface(self) -> None:
        class FakeRGBA:
            def __init__(self) -> None:
                self.red = 0.0
                self.green = 0.0
                self.blue = 0.0
                self.alpha = 0.0

        class GdkModule:
            RGBA = FakeRGBA

        color = embedded_webview.build_webview_background_rgba(GdkModule)

        self.assertIsNotNone(color)
        self.assertAlmostEqual(color.red, 9 / 255)
        self.assertAlmostEqual(color.green, 16 / 255)
        self.assertAlmostEqual(color.blue, 25 / 255)
        self.assertEqual(color.alpha, 1.0)

    def test_apply_webview_background_color_sets_dark_background_when_supported(self) -> None:
        class FakeRGBA:
            def __init__(self) -> None:
                self.red = 0.0
                self.green = 0.0
                self.blue = 0.0
                self.alpha = 0.0

        class GdkModule:
            RGBA = FakeRGBA

        class FakeWebView:
            def __init__(self) -> None:
                self.received = None

            def set_background_color(self, color) -> None:
                self.received = color

        webview = FakeWebView()

        applied = embedded_webview.apply_webview_background_color(webview, GdkModule)

        self.assertTrue(applied)
        self.assertIsNotNone(webview.received)
        self.assertAlmostEqual(webview.received.red, 9 / 255)
        self.assertAlmostEqual(webview.received.green, 16 / 255)
        self.assertAlmostEqual(webview.received.blue, 25 / 255)
        self.assertEqual(webview.received.alpha, 1.0)

    def test_build_embedded_window_css_targets_window_and_root_container(self) -> None:
        css = embedded_webview.build_embedded_window_css().decode("utf-8")

        self.assertIn("window.subvost-embedded-window", css)
        self.assertIn("box.subvost-embedded-root", css)
        self.assertIn("webview", css)
        self.assertIn("#091019", css)

    def test_add_css_class_uses_widget_style_context(self) -> None:
        class FakeStyleContext:
            def __init__(self) -> None:
                self.classes: list[str] = []

            def add_class(self, css_class: str) -> None:
                self.classes.append(css_class)

        class FakeWidget:
            def __init__(self) -> None:
                self.style_context = FakeStyleContext()

            def get_style_context(self) -> FakeStyleContext:
                return self.style_context

        widget = FakeWidget()

        applied = embedded_webview.add_css_class(widget, "subvost-embedded-window")

        self.assertTrue(applied)
        self.assertEqual(widget.style_context.classes, ["subvost-embedded-window"])

    def test_apply_window_background_css_registers_provider_for_display(self) -> None:
        class FakeStyleContext:
            def __init__(self) -> None:
                self.classes: list[str] = []

            def add_class(self, css_class: str) -> None:
                self.classes.append(css_class)

        class FakeWindow:
            def __init__(self) -> None:
                self.style_context = FakeStyleContext()

            def get_style_context(self) -> FakeStyleContext:
                return self.style_context

        class FakeCssProvider:
            def __init__(self) -> None:
                self.loaded = None

            def load_from_data(self, payload: bytes) -> None:
                self.loaded = payload

        class FakeDisplay:
            @staticmethod
            def get_default() -> str:
                return "display"

        class FakeGtkModule:
            STYLE_PROVIDER_PRIORITY_APPLICATION = 777
            CssProvider = FakeCssProvider

            class StyleContext:
                calls: list[tuple[object, object, int]] = []

                @staticmethod
                def add_provider_for_display(display, provider, priority: int) -> None:
                    FakeGtkModule.StyleContext.calls.append((display, provider, priority))

        class FakeGdkModule:
            Display = FakeDisplay

        window = FakeWindow()

        provider = embedded_webview.apply_window_background_css(window, FakeGtkModule, FakeGdkModule)

        self.assertIsNotNone(provider)
        self.assertEqual(window.style_context.classes, ["subvost-embedded-window"])
        self.assertEqual(len(FakeGtkModule.StyleContext.calls), 1)
        display, registered_provider, priority = FakeGtkModule.StyleContext.calls[0]
        self.assertEqual(display, "display")
        self.assertIs(registered_provider, provider)
        self.assertEqual(priority, 777)
        self.assertIn(b"#091019", provider.loaded)

    def test_build_webview_container_marks_root_container_and_expands(self) -> None:
        class FakeStyleContext:
            def __init__(self) -> None:
                self.classes: list[str] = []

            def add_class(self, css_class: str) -> None:
                self.classes.append(css_class)

        class FakeBox:
            def __init__(self, orientation=None) -> None:
                self.orientation = orientation
                self.hexpand = None
                self.vexpand = None
                self.style_context = FakeStyleContext()

            def set_hexpand(self, value: bool) -> None:
                self.hexpand = value

            def set_vexpand(self, value: bool) -> None:
                self.vexpand = value

            def get_style_context(self) -> FakeStyleContext:
                return self.style_context

        class FakeOrientation:
            VERTICAL = "vertical"

        class FakeGtkModule:
            Box = FakeBox
            Orientation = FakeOrientation

        container = embedded_webview.build_webview_container(FakeGtkModule)

        self.assertEqual(container.orientation, "vertical")
        self.assertTrue(container.hexpand)
        self.assertTrue(container.vexpand)
        self.assertEqual(container.style_context.classes, ["subvost-embedded-root"])

    def test_request_application_shutdown_posts_json_payload(self) -> None:
        seen: dict[str, object] = {}

        def fake_urlopen(request, timeout: float):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["headers"] = {key.lower(): value for key, value in request.header_items()}
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"ok": True, "message": "closing"})

        payload = embedded_webview.request_application_shutdown(
            "http://127.0.0.1:8421",
            source="window-close",
            timeout=17,
            urlopen=fake_urlopen,
        )

        self.assertEqual(payload["message"], "closing")
        self.assertEqual(seen["url"], "http://127.0.0.1:8421/api/app/terminate")
        self.assertEqual(seen["timeout"], 17)
        self.assertEqual(seen["headers"]["content-type"], "application/json")
        self.assertEqual(seen["body"], {"source": "window-close"})

    def test_request_gui_backend_shutdown_posts_to_gui_only_route(self) -> None:
        seen: dict[str, object] = {}

        def fake_urlopen(request, timeout: float):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["headers"] = {key.lower(): value for key, value in request.header_items()}
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"ok": True, "message": "gui closing", "vpn_stop_requested": False})

        payload = embedded_webview.request_gui_backend_shutdown(
            "http://127.0.0.1:8421",
            source="window-close",
            timeout=17,
            urlopen=fake_urlopen,
        )

        self.assertEqual(payload["message"], "gui closing")
        self.assertFalse(payload["vpn_stop_requested"])
        self.assertEqual(seen["url"], "http://127.0.0.1:8421/api/app/shutdown-gui")
        self.assertEqual(seen["timeout"], 17)
        self.assertEqual(seen["headers"]["content-type"], "application/json")
        self.assertEqual(seen["body"], {"source": "window-close"})

    def test_request_application_shutdown_raises_backend_message_from_http_error(self) -> None:
        error = urllib.error.HTTPError(
            "http://127.0.0.1:8421/api/app/terminate",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"stop failed"}'),
        )

        def fake_urlopen(_request, timeout: float):
            raise error

        with self.assertRaisesRegex(RuntimeError, "stop failed"):
            embedded_webview.request_application_shutdown("http://127.0.0.1:8421", urlopen=fake_urlopen)

    def test_close_application_quits_after_successful_gui_shutdown(self) -> None:
        class FakeApp:
            def __init__(self) -> None:
                self.quit_calls = 0

            def quit(self) -> None:
                self.quit_calls += 1

        app = object.__new__(embedded_webview.EmbeddedWebViewApp)
        app.app = FakeApp()
        app.shutting_down = False
        app.request_gui_shutdown = lambda: {"ok": True, "vpn_stop_requested": False}
        app.show_shutdown_error = lambda _message: self.fail("Диалог ошибки не должен открываться")

        closed = embedded_webview.EmbeddedWebViewApp.close_application(app)

        self.assertTrue(closed)
        self.assertTrue(app.shutting_down)
        self.assertEqual(app.app.quit_calls, 1)

    def test_close_application_blocks_window_close_on_shutdown_error(self) -> None:
        class FakeApp:
            def __init__(self) -> None:
                self.quit_calls = 0

            def quit(self) -> None:
                self.quit_calls += 1

        shown_errors: list[str] = []
        app = object.__new__(embedded_webview.EmbeddedWebViewApp)
        app.app = FakeApp()
        app.shutting_down = False

        def fail_shutdown():
            raise RuntimeError("stop failed")

        app.request_gui_shutdown = fail_shutdown
        app.show_shutdown_error = shown_errors.append

        closed = embedded_webview.EmbeddedWebViewApp.close_application(app)

        self.assertFalse(closed)
        self.assertFalse(app.shutting_down)
        self.assertEqual(app.app.quit_calls, 0)
        self.assertEqual(shown_errors, ["stop failed"])


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
