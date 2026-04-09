from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import native_shell_app  # noqa: E402
from native_shell_shared import build_tray_support  # noqa: E402


class FakeGtkSettings:
    def __init__(self, dark_preference: bool) -> None:
        self.dark_preference = dark_preference
        self.calls: list[bool] = []

    def get_property(self, property_name: str) -> bool:
        if property_name != "gtk-application-prefer-dark-theme":
            raise AssertionError(property_name)
        return self.dark_preference

    def set_property(self, property_name: str, value: bool) -> None:
        if property_name != "gtk-application-prefer-dark-theme":
            raise AssertionError(property_name)
        self.calls.append(bool(value))
        self.dark_preference = bool(value)


class FakeWindow:
    def __init__(self, visible: bool) -> None:
        self.visible = visible
        self.present_calls = 0

    def get_visible(self) -> bool:
        return self.visible

    def present(self) -> None:
        self.present_calls += 1
        self.visible = True


class NativeShellAppTests(unittest.TestCase):
    def make_app(self) -> native_shell_app.NativeShellApp:
        app = native_shell_app.NativeShellApp.__new__(native_shell_app.NativeShellApp)
        app.tray_support = build_tray_support(
            watcher_name="org.kde.StatusNotifierWatcher",
            indicator_candidate=("AyatanaAppIndicator3", "0.1", "Ayatana AppIndicator"),
        )
        app.tray_process = object()
        app.log_lines = []
        app.allow_close = False
        app.initial_gtk_dark_theme_preference = None
        app.did_capture_initial_theme_preference = False
        app.append_log = lambda source, message: app.log_lines.append((source, message))
        app.set_status = lambda message: setattr(app, "status_message", message)
        app.refresh_status_after_settings_change = lambda: setattr(app, "refresh_called", True)
        app.refresh_called = False
        app.status_message = ""
        return app

    def test_apply_theme_preference_restores_initial_system_preference(self) -> None:
        fake_settings = FakeGtkSettings(dark_preference=True)

        class FakeGtkModule:
            class Settings:
                @staticmethod
                def get_default() -> FakeGtkSettings:
                    return fake_settings

        app = self.make_app()
        app.Gtk = FakeGtkModule

        app.apply_theme_preference("light")
        app.apply_theme_preference("system")

        self.assertEqual(app.initial_gtk_dark_theme_preference, True)
        self.assertEqual(fake_settings.calls, [False, True])

    def test_handle_tray_helper_failure_shows_hidden_window(self) -> None:
        app = self.make_app()
        app.window = FakeWindow(visible=False)

        app.handle_tray_helper_failure(2, stage="startup")

        self.assertFalse(app.tray_support.available)
        self.assertIsNone(app.tray_process)
        self.assertEqual(app.window.present_calls, 1)
        self.assertIn("автоматически показано", app.status_message)
        self.assertFalse(app.refresh_called)
        self.assertTrue(any("автоматически показано" in message for _source, message in app.log_lines))

    def test_handle_tray_helper_failure_refreshes_status_when_window_already_visible(self) -> None:
        app = self.make_app()
        app.window = FakeWindow(visible=True)

        app.handle_tray_helper_failure(3, stage="runtime")

        self.assertFalse(app.tray_support.available)
        self.assertIsNone(app.tray_process)
        self.assertEqual(app.window.present_calls, 0)
        self.assertTrue(app.refresh_called)

    def test_finish_runtime_action_updates_status_and_log_on_success(self) -> None:
        app = self.make_app()
        app.action_in_flight = "start-runtime"
        app.dashboard_action_buttons = {}
        app.dashboard_labels = {}
        app.dashboard_metrics = {}
        app.last_status_payload = None
        app.refresh_dashboard_controls = lambda: setattr(app, "controls_refreshed", True)
        app.controls_refreshed = False
        app.update_dashboard_from_status = lambda payload: setattr(app, "dashboard_payload", payload)

        payload = {
            "last_action": {
                "message": "Запуск завершён успешно.",
            }
        }

        result = app.finish_runtime_action("start-runtime", "tray", True, payload)

        self.assertFalse(result)
        self.assertIsNone(app.action_in_flight)
        self.assertEqual(app.status_message, "Запуск завершён успешно.")
        self.assertEqual(app.dashboard_payload, payload)
        self.assertTrue(app.controls_refreshed)
        self.assertTrue(any("Запуск завершён успешно." in message for _source, message in app.log_lines))


if __name__ == "__main__":
    unittest.main()
