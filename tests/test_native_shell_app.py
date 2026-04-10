from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


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


class FakeEntry:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def set_text(self, value: str) -> None:
        self.text = value

    def get_text(self) -> str:
        return self.text


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
        app.last_store_payload = None
        app.last_status_payload = None
        app.selected_subscription_id = None
        app.subscription_url_entry = None
        app.routing_import_buffer = None
        app.shell_log_entries = []
        app.log_filter = "all"
        app.log_filter_buttons = {}
        app.log_copy_button = None
        app.log_export_button = None
        app.log_summary_label = None
        app.log_meta_label = None
        app.log_export_label = None
        app.log_buffer = None
        app.log_path = REPO_ROOT / "logs" / "native-shell.log"
        app.last_log_export_path = None
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
        app.refresh_subscriptions_controls = lambda: setattr(app, "subscriptions_controls_refreshed", True)
        app.controls_refreshed = False
        app.subscriptions_controls_refreshed = False
        app.update_dashboard_from_status = lambda payload: setattr(app, "dashboard_payload", payload)
        app.render_subscriptions_view = lambda: setattr(app, "subscriptions_rendered", True)
        app.subscriptions_rendered = False

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
        self.assertTrue(app.subscriptions_controls_refreshed)
        self.assertTrue(app.subscriptions_rendered)
        self.assertTrue(any("Запуск завершён успешно." in message for _source, message in app.log_lines))

    def test_apply_combined_snapshot_syncs_selected_subscription_id(self) -> None:
        app = self.make_app()
        app.selected_subscription_id = "missing"
        app.update_dashboard_from_status = lambda payload: setattr(app, "dashboard_payload", payload)
        app.render_subscriptions_view = lambda: setattr(app, "subscriptions_rendered", True)
        app.subscriptions_rendered = False

        payload = {
            "status": {"summary": {"state": "stopped"}},
            "store": {
                "store": {
                    "subscriptions": [
                        {"id": "sub-2", "profile_id": "profile-2"},
                    ],
                    "profiles": [],
                    "routing": {},
                },
                "active_profile": {"id": "profile-2", "source_subscription_id": "sub-2"},
            },
        }

        app.apply_combined_snapshot(payload)

        self.assertEqual(app.selected_subscription_id, "sub-2")
        self.assertEqual(app.dashboard_payload, {"summary": {"state": "stopped"}})
        self.assertEqual(app.last_store_payload, payload["store"])
        self.assertTrue(app.subscriptions_rendered)

    def test_finish_store_action_clears_url_and_focuses_new_subscription(self) -> None:
        app = self.make_app()
        app.action_in_flight = "subscriptions-add"
        app.subscription_url_entry = FakeEntry("https://example.com/subscription")
        app.apply_combined_snapshot = lambda payload: setattr(app, "combined_payload", payload)
        app.refresh_dashboard_controls = lambda: setattr(app, "controls_refreshed", True)
        app.refresh_subscriptions_controls = lambda: setattr(app, "subscriptions_controls_refreshed", True)
        app.controls_refreshed = False
        app.subscriptions_controls_refreshed = False

        payload = {
            "message": "Подписка добавлена.",
            "subscription": {"id": "sub-1"},
            "store": {"store": {"subscriptions": [{"id": "sub-1"}]}, "active_profile": None},
            "status": {"summary": {"state": "stopped"}},
        }

        result = app.finish_store_action("subscriptions-add", "window", True, payload)

        self.assertFalse(result)
        self.assertIsNone(app.action_in_flight)
        self.assertEqual(app.subscription_url_entry.text, "")
        self.assertEqual(app.selected_subscription_id, "sub-1")
        self.assertEqual(app.combined_payload, payload)
        self.assertEqual(app.status_message, "Подписка добавлена.")
        self.assertTrue(app.controls_refreshed)
        self.assertTrue(app.subscriptions_controls_refreshed)

    def test_finish_store_action_uses_status_payload_for_ping_result(self) -> None:
        app = self.make_app()
        app.action_in_flight = "node-ping"
        app.apply_status_payload = lambda payload: setattr(app, "status_payload_applied", payload)
        app.refresh_dashboard_controls = lambda: setattr(app, "controls_refreshed", True)
        app.refresh_subscriptions_controls = lambda: setattr(app, "subscriptions_controls_refreshed", True)
        app.controls_refreshed = False
        app.subscriptions_controls_refreshed = False

        payload = {
            "status": {
                "last_action": {
                    "message": "Узел 'Edge' ответил за 12.4 мс.",
                }
            }
        }

        result = app.finish_store_action("node-ping", "window", True, payload)

        self.assertFalse(result)
        self.assertEqual(app.status_payload_applied, payload["status"])
        self.assertEqual(app.status_message, "Узел 'Edge' ответил за 12.4 мс.")
        self.assertTrue(app.controls_refreshed)
        self.assertTrue(app.subscriptions_controls_refreshed)


if __name__ == "__main__":
    unittest.main()
