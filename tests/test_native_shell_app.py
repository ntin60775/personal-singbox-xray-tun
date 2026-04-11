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

    def test_apply_theme_preference_forces_dark_contract(self) -> None:
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

        self.assertEqual(fake_settings.calls, [True, True])

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

    def test_update_dashboard_uses_compact_message_for_foreign_bundle(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.set_metric_value = lambda key, value: captured.__setitem__(f"metric:{key}", value)
        app.refresh_dashboard_badges = lambda badges, state: captured.__setitem__("badges", f"{state}:{len(badges)}")
        app.refresh_dashboard_controls = lambda: None

        app.update_dashboard_from_status(
            {
                "summary": {
                    "state": "degraded",
                    "label": "Активен другой bundle",
                    "description": "Обнаружен runtime другой копии bundle. Интерфейс: tun0.",
                    "tun_line": "tun0 готов",
                    "dns_line": "1.1.1.1",
                    "badges": ["Активен другой bundle"],
                },
                "runtime": {
                    "start_blocked": True,
                    "ownership": "foreign",
                    "ownership_label": "Другой bundle",
                },
                "connection": {
                    "protocol_label": "VLESS",
                    "transport_label": "TCP",
                    "security_label": "Reality",
                    "active_name": "Node",
                    "remote_endpoint": "edge.example.com:443",
                    "remote_sni": "edge.example.com",
                },
                "routing": {"enabled": False},
                "traffic": {},
                "artifacts": {},
                "active_node": {"name": "Node"},
                "last_action": {},
                "project_root": "/tmp/project",
                "logs": {},
            }
        )

        self.assertEqual(captured["hero_detail"], "Управление локальным runtime заблокировано: активен другой bundle.")

    def test_refresh_dashboard_controls_uses_compact_foreign_bundle_action_hint(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.dashboard_action_buttons = {}
        app.last_status_payload = {
            "summary": {"state": "degraded"},
            "runtime": {
                "start_blocked": True,
                "ownership": "foreign",
                "next_start_reason": (
                    "Обнаружен runtime другого bundle. Bundle-владелец: /foreign/project. "
                    "Текущий bundle: /current/project. Сначала остановите или проверьте исходный bundle, затем повторите запуск."
                ),
            },
        }

        app.refresh_dashboard_controls()

        self.assertEqual(captured["action_hint"], "Остановите исходный bundle, затем повторите запуск.")

    def test_visible_log_text_respects_filter_and_separates_sources(self) -> None:
        app = self.make_app()
        app.log_filter = "error"
        app.shell_log_entries = [
            {
                "timestamp": "2026-04-10T10:05:00",
                "name": "tray",
                "level": "warning",
                "message": "Tray helper завершился.",
                "details": "",
                "source": "shell",
            }
        ]
        app.last_status_payload = {
            "logs": {
                "entries": [
                    {
                        "timestamp": "2026-04-10T10:04:00",
                        "name": "xray",
                        "level": "error",
                        "message": "fatal: runtime crashed",
                        "details": "traceback",
                        "source": "file",
                    }
                ]
            }
        }

        rendered = app.visible_log_text()

        self.assertIn("Фильтр: Ошибки", rendered)
        self.assertIn("=== Native shell (0) ===", rendered)
        self.assertIn("=== Bundle и runtime (1) ===", rendered)
        self.assertIn("fatal: runtime crashed", rendered)
        self.assertNotIn("Tray helper завершился.", rendered)

    def test_export_visible_log_writes_file_into_log_dir(self) -> None:
        app = self.make_app()
        app.append_log = lambda source, message: app.log_lines.append((source, message))
        app.log_lines = []
        app.last_status_payload = {
            "logs": {
                "entries": [
                    {
                        "timestamp": "2026-04-10T10:04:00",
                        "name": "xray",
                        "level": "error",
                        "message": "fatal: runtime crashed",
                        "details": "",
                        "source": "file",
                    }
                ]
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            app.runtime_service = SimpleNamespace(context=SimpleNamespace(log_dir=log_dir))

            app.export_visible_log()

            exports = sorted(log_dir.glob("native-shell-log-export-*.log"))
            self.assertEqual(len(exports), 1)
            self.assertIn("fatal: runtime crashed", exports[0].read_text(encoding="utf-8"))
            self.assertEqual(app.last_log_export_path, exports[0])
            self.assertIn(str(exports[0]), app.status_message)
            self.assertTrue(any("экспортирован" in message.lower() for _source, message in app.log_lines))


if __name__ == "__main__":
    unittest.main()
