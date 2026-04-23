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


class FakeButton:
    def __init__(self) -> None:
        self.label = ""
        self.sensitive = True
        self.tooltip = None
        self.variant = None
        self.visible = True

    def set_label(self, value: str) -> None:
        self.label = value

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)

    def set_tooltip_text(self, value: str) -> None:
        self.tooltip = value

    def set_visible(self, value: bool) -> None:
        self.visible = bool(value)


class FakeLabel:
    def __init__(self) -> None:
        self.label = ""
        self.classes: set[str] = set()

    def set_label(self, value: str) -> None:
        self.label = value

    def add_css_class(self, value: str) -> None:
        self.classes.add(value)

    def remove_css_class(self, value: str) -> None:
        self.classes.discard(value)


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
        app.stack = None
        app.append_log = lambda source, message: app.log_lines.append((source, message))
        app.set_status = lambda message: setattr(app, "status_message", message)
        app.refresh_status_after_settings_change = lambda: setattr(app, "refresh_called", True)
        app.refresh_called = False
        app.status_message = ""
        app.last_store_payload = None
        app.last_status_payload = None
        app.selected_subscription_id = None
        app.subscription_url_entry = None
        app.dashboard_node_grid_box = None
        app.dashboard_node_grid_scroller = None
        app.dashboard_node_empty_label = None
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
        app.diagnostic_labels = {}
        app.dashboard_labels = {}
        app.dashboard_metrics = {}
        app.dashboard_action_buttons = {}
        app.dashboard_primary_action_id = None
        app.dashboard_badge_box = None
        app.dashboard_status_meta_box = None
        app.dashboard_conflict_bar = None
        app.dashboard_conflict_label = None
        app.dashboard_takeover_button = None
        app.diagnostic_takeover_button = None
        app.diagnostic_action_label = None
        app.settings_update_button = None
        app.settings_update_feedback_label = None
        app.dashboard_dns_button = None
        app.dashboard_dns_compact_text = "—"
        app.dashboard_dns_full_text = "—"
        app.dashboard_dns_server_count = 0
        app.dashboard_dns_expanded = False
        app.dashboard_tun_line = "—"
        app.dashboard_uptime_source_id = None
        app.node_row_click_suppressed = False
        app.action_in_flight = None
        app.log_path = REPO_ROOT / "logs" / "native-shell.log"
        app.last_log_export_path = None
        return app

    def test_native_shell_uses_named_app_icon(self) -> None:
        self.assertEqual(native_shell_app.APP_ICON_NAME, "subvost-xray-tun-icon")

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

    def test_subscriptions_page_title_is_shortened_to_subscriptions(self) -> None:
        page = next(page for page in native_shell_app.NATIVE_SHELL_PAGES if page.page_id == "subscriptions")

        self.assertEqual(page.title, "Подписки")

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

    def test_takeover_button_starts_takeover_runtime_action(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.begin_runtime_action = lambda action_id, *, source: captured.update({"action_id": action_id, "source": source})

        app.on_takeover_requested(None)

        self.assertEqual(captured, {"action_id": "takeover-runtime", "source": "window"})

    def test_run_runtime_action_worker_dispatches_takeover_runtime(self) -> None:
        app = self.make_app()
        calls: list[str] = []
        app.runtime_service = SimpleNamespace(
            start_runtime=lambda: {"action": "start"},
            stop_runtime=lambda: {"action": "stop"},
            takeover_runtime=lambda: calls.append("takeover") or {"action": "takeover"},
            cleanup_runtime_artifacts=lambda: {"action": "cleanup"},
            capture_diagnostics=lambda: {"action": "diag"},
            update_xray_core=lambda: calls.append("update-xray") or {"action": "update-xray"},
        )
        app.GLib = SimpleNamespace(idle_add=lambda func, *args: func(*args))
        captured: dict[str, object] = {}
        app.finish_runtime_action = lambda action_id, source, ok, payload: captured.update(
            {"action_id": action_id, "source": source, "ok": ok, "payload": payload}
        ) or False

        app.run_runtime_action_worker("takeover-runtime", "window")

        self.assertEqual(calls, ["takeover"])
        self.assertEqual(captured["action_id"], "takeover-runtime")
        self.assertEqual(captured["source"], "window")
        self.assertTrue(captured["ok"])
        self.assertEqual(captured["payload"], {"action": "takeover"})

        captured.clear()
        app.run_runtime_action_worker("cleanup-artifacts", "diagnostics")

        self.assertEqual(captured["action_id"], "cleanup-artifacts")
        self.assertEqual(captured["source"], "diagnostics")
        self.assertTrue(captured["ok"])
        self.assertEqual(captured["payload"], {"action": "cleanup"})

        captured.clear()
        app.run_runtime_action_worker("update-xray-core", "settings")

        self.assertEqual(calls, ["takeover", "update-xray"])
        self.assertEqual(captured["action_id"], "update-xray-core")
        self.assertEqual(captured["source"], "settings")
        self.assertTrue(captured["ok"])
        self.assertEqual(captured["payload"], {"action": "update-xray"})

    def test_cleanup_artifacts_button_starts_diagnostics_cleanup_action(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.begin_runtime_action = lambda action_id, *, source: captured.update({"action_id": action_id, "source": source})

        app.on_cleanup_artifacts_clicked(None)

        self.assertEqual(captured, {"action_id": "cleanup-artifacts", "source": "diagnostics"})

    def test_update_xray_core_button_starts_settings_action(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.begin_runtime_action = lambda action_id, *, source: captured.update({"action_id": action_id, "source": source})

        app.on_update_xray_core_clicked(None)

        self.assertEqual(captured, {"action_id": "update-xray-core", "source": "settings"})

    def test_settings_update_feedback_tracks_update_lifecycle(self) -> None:
        app = self.make_app()
        app.settings_update_feedback_label = FakeLabel()
        app.action_in_flight = "update-xray-core"
        app.apply_status_payload = lambda payload: setattr(app, "dashboard_payload", payload)
        app.refresh_dashboard_controls = lambda: setattr(app, "controls_refreshed", True)
        app.refresh_settings_controls = lambda: setattr(app, "settings_controls_refreshed", True)
        app.refresh_subscriptions_controls = lambda: setattr(app, "subscriptions_controls_refreshed", True)
        app.controls_refreshed = False
        app.settings_controls_refreshed = False
        app.subscriptions_controls_refreshed = False

        app.set_settings_update_feedback("busy", "Обновление ядра Xray выполняется.")

        self.assertEqual(app.settings_update_feedback_label.label, "Обновление ядра Xray выполняется.")
        self.assertIn("native-shell-action-feedback-busy", app.settings_update_feedback_label.classes)

        payload = {"last_action": {"message": "Ядро Xray обновлено."}}
        app.finish_runtime_action("update-xray-core", "settings", True, payload)

        self.assertEqual(app.settings_update_feedback_label.label, "Ядро Xray обновлено.")
        self.assertNotIn("native-shell-action-feedback-busy", app.settings_update_feedback_label.classes)
        self.assertIn("native-shell-action-feedback-success", app.settings_update_feedback_label.classes)
        self.assertTrue(app.controls_refreshed)
        self.assertTrue(app.settings_controls_refreshed)
        self.assertTrue(app.subscriptions_controls_refreshed)

    def test_diagnostics_action_feedback_tracks_cleanup_lifecycle(self) -> None:
        app = self.make_app()
        app.diagnostic_action_label = FakeLabel()
        app.action_in_flight = "cleanup-artifacts"
        app.apply_status_payload = lambda payload: setattr(app, "dashboard_payload", payload)
        app.refresh_dashboard_controls = lambda: setattr(app, "controls_refreshed", True)
        app.refresh_subscriptions_controls = lambda: setattr(app, "subscriptions_controls_refreshed", True)
        app.controls_refreshed = False
        app.subscriptions_controls_refreshed = False

        app.set_diagnostic_action_feedback("busy", "Очистить служебные файлы: выполняется.")

        self.assertEqual(app.diagnostic_action_label.label, "Очистить служебные файлы: выполняется.")
        self.assertIn("native-shell-action-feedback-busy", app.diagnostic_action_label.classes)

        payload = {"last_action": {"message": "Служебные файлы очищены."}}
        app.finish_runtime_action("cleanup-artifacts", "diagnostics", True, payload)

        self.assertEqual(app.diagnostic_action_label.label, "Служебные файлы очищены.")
        self.assertNotIn("native-shell-action-feedback-busy", app.diagnostic_action_label.classes)
        self.assertIn("native-shell-action-feedback-success", app.diagnostic_action_label.classes)
        self.assertTrue(app.controls_refreshed)
        self.assertTrue(app.subscriptions_controls_refreshed)

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
        app.set_diagnostic_label = lambda key, value: captured.__setitem__(f"diag:{key}", value)
        app.set_metric_value = lambda key, value: captured.__setitem__(f"metric:{key}", value)
        app.refresh_dashboard_badges = lambda **kwargs: captured.__setitem__("badges", str(kwargs))
        app.refresh_dashboard_controls = lambda: None
        app.update_dashboard_conflict_bar = lambda runtime: captured.__setitem__("conflict", str(runtime.get("ownership")))
        app.update_dashboard_state_icon = lambda summary, runtime: captured.__setitem__("state_icon", str(summary.get("state")))

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
                    "stack_is_live": True,
                    "ownership": "foreign",
                    "ownership_label": "Другой bundle",
                    "state_bundle_project_root": "/foreign/project",
                    "config_origin": "generated",
                    "active_xray_config": "/tmp/generated.json",
                },
                "connection": {
                    "protocol_label": "VLESS",
                    "transport_label": "TCP",
                    "security_label": "Reality",
                    "active_name": "Node",
                    "remote_endpoint": "edge.example.com:443",
                    "remote_sni": "edge.example.com",
                    "tun_interface": "tun0",
                    "dns_servers": "1.1.1.1, 8.8.8.8",
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

        self.assertEqual(captured["hero_state"], "Подключение недоступно")
        self.assertEqual(captured["hero_active"], "Node · VLESS")
        self.assertIn("Где он запущен: /foreign/project", captured["diag:diagnostic_instance"])
        self.assertIn("Сгенерированный конфиг", captured["diag:diagnostic_files"])
        self.assertIn("TUN: tun0 готов", captured["diag:diagnostic_connection"])
        self.assertIn("DNS: 1.1.1.1, 8.8.8.8", captured["diag:diagnostic_connection"])

    def test_refresh_dashboard_controls_uses_compact_foreign_bundle_action_hint(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.dashboard_action_buttons = {
            "primary-connect": FakeButton(),
            "open-subscriptions": FakeButton(),
            "capture-diagnostics": FakeButton(),
            "open-diagnostics": FakeButton(),
        }
        app.set_button_variant = lambda button, variant: setattr(button, "variant", variant)
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

        self.assertEqual(captured["action_hint"], "")
        self.assertEqual(app.dashboard_action_buttons["primary-connect"].label, "Подключиться")
        self.assertFalse(app.dashboard_action_buttons["primary-connect"].sensitive)

    def test_refresh_dashboard_controls_exposes_connect_button_for_last_selected_node(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.dashboard_action_buttons = {
            "primary-connect": FakeButton(),
            "open-subscriptions": FakeButton(),
            "capture-diagnostics": FakeButton(),
            "open-diagnostics": FakeButton(),
        }
        app.set_button_variant = lambda button, variant: setattr(button, "variant", variant)
        app.last_status_payload = {
            "summary": {"state": "stopped"},
            "runtime": {"start_ready": True, "stop_allowed": True, "start_blocked": False},
            "processes": {"xray_alive": False, "tun_present": False},
            "connection": {"protocol_label": "VLESS", "active_name": "Финляндия"},
            "active_node": {"name": "Финляндия"},
        }

        app.refresh_dashboard_controls()

        self.assertEqual(app.dashboard_primary_action_id, "start-runtime")
        self.assertEqual(app.dashboard_action_buttons["primary-connect"].label, "Подключиться")
        self.assertTrue(app.dashboard_action_buttons["primary-connect"].sensitive)
        self.assertEqual(app.dashboard_action_buttons["primary-connect"].variant, "primary")
        self.assertEqual(captured["action_summary"], "Готово к запуску через узел: Финляндия · VLESS.")
        self.assertEqual(captured["action_hint"], "")

    def test_refresh_subscriptions_controls_enables_prepare_geodata_for_single_enabled_profile(self) -> None:
        app = self.make_app()
        app.subscription_action_buttons = {}
        app.routing_action_buttons = {
            "routing-import": FakeButton(),
            "routing-prepare-geodata": FakeButton(),
            "routing-toggle": FakeButton(),
            "routing-clear-active": FakeButton(),
        }
        app.last_store_payload = {
            "store": {
                "subscriptions": [],
                "profiles": [],
                "routing": {
                    "enabled": False,
                    "profiles": [
                        {"id": "routing-1", "enabled": True},
                    ],
                },
            },
            "active_routing_profile": None,
        }

        app.refresh_subscriptions_controls()

        self.assertTrue(app.routing_action_buttons["routing-import"].sensitive)
        self.assertTrue(app.routing_action_buttons["routing-prepare-geodata"].sensitive)
        self.assertFalse(app.routing_action_buttons["routing-toggle"].sensitive)
        self.assertFalse(app.routing_action_buttons["routing-clear-active"].sensitive)

    def test_dashboard_primary_action_spec_points_to_dashboard_node_cards_when_node_missing(self) -> None:
        app = self.make_app()
        app.last_status_payload = {
            "summary": {"state": "stopped"},
            "runtime": {"stop_allowed": True},
            "processes": {"xray_alive": False, "tun_present": False},
            "connection": {},
            "active_node": {},
        }

        spec = app.dashboard_primary_action_spec()

        self.assertIsNone(spec["action_id"])
        self.assertEqual(spec["summary"], "Выберите узел ниже на этой вкладке.")
        self.assertEqual(spec["tooltip"], "Сначала выберите узел в карточках ниже.")

    def test_refresh_dashboard_controls_switches_primary_button_to_disconnect(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.dashboard_action_buttons = {
            "primary-connect": FakeButton(),
            "open-subscriptions": FakeButton(),
            "capture-diagnostics": FakeButton(),
            "open-diagnostics": FakeButton(),
        }
        app.set_button_variant = lambda button, variant: setattr(button, "variant", variant)
        app.last_status_payload = {
            "summary": {"state": "running"},
            "runtime": {"start_blocked": False, "stop_allowed": True},
            "processes": {"xray_alive": True, "tun_present": True},
            "connection": {"protocol_label": "VLESS", "active_name": "Финляндия"},
            "active_node": {"name": "Финляндия"},
        }

        app.refresh_dashboard_controls()

        self.assertEqual(app.dashboard_primary_action_id, "stop-runtime")
        self.assertEqual(app.dashboard_action_buttons["primary-connect"].label, "Отключиться")
        self.assertEqual(app.dashboard_action_buttons["primary-connect"].variant, "danger")
        self.assertEqual(captured["action_summary"], "Сейчас подключено через узел: Финляндия · VLESS.")

    def test_update_dashboard_appends_subscription_to_active_node_line(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.last_store_payload = {
            "store": {
                "subscriptions": [
                    {"id": "sub-1", "profile_id": "profile-1", "url": "https://sub.subvost.fun/profile"},
                ],
            },
            "active_profile": {"id": "profile-1", "source_subscription_id": "sub-1"},
        }
        app.set_dashboard_label = lambda key, value: captured.__setitem__(key, value)
        app.set_diagnostic_label = lambda key, value: captured.__setitem__(f"diag:{key}", value)
        app.set_metric_value = lambda key, value: captured.__setitem__(f"metric:{key}", value)
        app.refresh_dashboard_badges = lambda **kwargs: captured.__setitem__("badges", str(kwargs))
        app.refresh_dashboard_controls = lambda: None
        app.update_dashboard_conflict_bar = lambda runtime: None
        app.update_dashboard_state_icon = lambda summary, runtime: None
        app.dashboard_labels = {
            "hero_active": FakeButton(),
            "hero_subscription": FakeButton(),
        }

        app.update_dashboard_from_status(
            {
                "summary": {"state": "stopped", "label": "Остановлено", "tun_line": "tun0 готов", "dns_line": "1.1.1.1"},
                "runtime": {},
                "connection": {"protocol_label": "VLESS", "active_name": "Финляндия"},
                "routing": {"enabled": False},
                "traffic": {},
                "artifacts": {},
                "active_node": {"name": "Финляндия"},
                "last_action": {},
                "project_root": "/tmp/project",
                "logs": {},
            }
        )

        self.assertEqual(captured["hero_active"], "Финляндия · VLESS")
        self.assertEqual(captured["hero_subscription"], "Подписка: sub.subvost.fun")

    def test_status_message_from_payload_humanizes_foreign_instance_conflict(self) -> None:
        app = self.make_app()

        message = app.status_message_from_payload(
            {
                "summary": {"description": "Обнаружен runtime другой копии bundle. Интерфейс: tun0."},
                "runtime": {"start_blocked": True, "ownership": "foreign"},
            }
        )

        self.assertEqual(message, "Снимок состояния обновлён.")

    def test_format_dns_summary_collapses_extra_addresses(self) -> None:
        app = self.make_app()

        summary, full, count = app.format_dns_summary("192.168.100.1, 1.1.1.1, 8.8.8.8, 9.9.9.9")

        self.assertEqual(summary, "192.168.100.1 + ещё 3")
        self.assertEqual(full, "192.168.100.1, 1.1.1.1, 8.8.8.8, 9.9.9.9")
        self.assertEqual(count, 4)

    def test_active_subscription_display_name_prefers_active_profile_source(self) -> None:
        app = self.make_app()
        app.last_store_payload = {
            "store": {
                "subscriptions": [
                    {"id": "sub-1", "profile_id": "profile-1", "url": "https://sub.subvost.fun/profile"},
                ],
            },
            "active_profile": {"id": "profile-1", "source_subscription_id": "sub-1"},
        }

        self.assertEqual(app.active_subscription_display_name(), "sub.subvost.fun")

    def test_refresh_dashboard_interface_metric_shows_full_dns_and_hides_button(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        dns_button = FakeButton()
        app.dashboard_dns_button = dns_button
        app.set_metric_value = lambda key, value: captured.__setitem__(key, value)
        app.dashboard_tun_line = "tun0 готов"
        app.dashboard_dns_compact_text = "192.168.100.1 + ещё 3"
        app.dashboard_dns_full_text = "192.168.100.1, fe80::1%eth0, 192.168.1.1, fe80::52ff:20ff:fe52:1234"
        app.dashboard_dns_server_count = 4

        app.refresh_dashboard_interface_metric()

        self.assertEqual(
            captured["interface"],
            "TUN: tun0 готов\nDNS (4):\n  Основной: 192.168.100.1\n  Доп.: fe80::1%eth0\n  Доп.: 192.168.1.1\n  Доп.: fe80::52ff:20ff:fe52:1234",
        )
        self.assertFalse(dns_button.visible)
        self.assertFalse(dns_button.sensitive)

    def test_dashboard_interface_text_keeps_single_dns_compact(self) -> None:
        app = self.make_app()

        self.assertEqual(app.dashboard_interface_text("tun0 готов", "192.168.100.1"), "TUN: tun0 готов\nDNS: 192.168.100.1")

    def test_dashboard_interface_markup_highlights_primary_dns(self) -> None:
        app = self.make_app()

        markup = app.dashboard_interface_markup("tun0 готов", "192.168.100.1, 1.1.1.1")

        self.assertIn("DNS (2):", markup)
        self.assertIn("Основной:", markup)
        self.assertIn("#7BC4FF", markup)

    def test_combine_rate_and_total_keeps_russian_total_label(self) -> None:
        app = self.make_app()

        self.assertEqual(app.combine_rate_and_total("43.1 KB/s", "5.2 GB"), "43.1 KB/s\nВсего: 5.2 GB")

    def test_dashboard_node_card_size_matches_fixed_four_column_grid(self) -> None:
        self.assertEqual(native_shell_app.DASHBOARD_NODE_CARD_COLUMNS, 4)
        self.assertEqual(native_shell_app.DASHBOARD_NODE_CARD_WIDTH, 283)
        self.assertEqual(native_shell_app.DASHBOARD_NODE_CARD_HEIGHT, 132)

    def test_node_card_meta_text_uses_protocol_endpoint_and_transport(self) -> None:
        app = self.make_app()

        meta = app.node_card_meta_text(
            {
                "protocol": "vless",
                "normalized": {
                    "address": "edge.example.com",
                    "port": 443,
                    "network": "tcp",
                },
            }
        )

        self.assertEqual(meta, "VLESS · edge.example.com:443 · транспорт=tcp")

    def test_node_display_name_strips_leading_flag(self) -> None:
        app = self.make_app()

        self.assertEqual(app.node_display_name("🇫🇮 Финляндия (Хельсинки)"), "Финляндия (Хельсинки)")
        self.assertEqual(app.node_display_name("", fallback=""), "")

    def test_connection_target_label_uses_name_without_flag_prefix(self) -> None:
        app = self.make_app()

        node_name, node_label = app.connection_target_label(
            {
                "active_node": {"name": "🇦🇹 Австрия (Вена)"},
                "connection": {"protocol_label": "VLESS"},
            }
        )

        self.assertEqual(node_name, "Австрия (Вена)")
        self.assertEqual(node_label, "Австрия (Вена) · VLESS")

    def test_on_node_card_released_activates_node(self) -> None:
        app = self.make_app()
        captured: dict[str, str] = {}
        app.begin_store_action = lambda action_id, **kwargs: captured.update({"action_id": action_id, **kwargs})

        app.on_node_card_released(None, 1, 0.0, 0.0, "profile-7", "node-3")

        self.assertEqual(captured, {"action_id": "node-activate", "profile_id": "profile-7", "node_id": "node-3"})

    def test_on_node_card_released_ignores_suppressed_click(self) -> None:
        app = self.make_app()
        app.node_row_click_suppressed = True
        app.begin_store_action = lambda *_args, **_kwargs: self.fail("node card click should be suppressed")

        app.on_node_card_released(None, 1, 0.0, 0.0, "profile-7", "node-3")

        self.assertFalse(app.node_row_click_suppressed)

    def test_dashboard_traffic_text_combines_speed_and_volume(self) -> None:
        app = self.make_app()

        text = app.dashboard_traffic_text(
            {
                "rx_rate_label": "43.1 KB/s",
                "tx_rate_label": "1.7 KB/s",
                "rx_total_label": "5.2 GB",
                "tx_total_label": "432.9 MB",
            }
        )

        self.assertEqual(text, "Скорость: 43.1 KB/s ↓ · 1.7 KB/s ↑\nОбъём: 5.2 GB ↓ · 432.9 MB ↑")

    def test_refresh_dashboard_live_status_line_shows_duration_for_active_connection(self) -> None:
        app = self.make_app()
        uptime_widget = FakeButton()
        traffic_widget = FakeButton()
        meta_box = FakeButton()
        app.dashboard_labels = {
            "hero_uptime": uptime_widget,
            "hero_traffic": traffic_widget,
        }
        app.dashboard_status_meta_box = meta_box
        app.last_status_payload = {
            "summary": {"state": "running"},
            "runtime": {"connected_since": "2026-04-11T12:00:00"},
            "processes": {"xray_alive": True, "tun_present": True},
            "traffic": {
                "rx_rate_label": "43.1 KB/s",
                "tx_rate_label": "1.7 KB/s",
                "rx_total_label": "5.2 GB",
                "tx_total_label": "432.9 MB",
            },
        }

        original_datetime = native_shell_app.datetime

        class FixedDateTime:
            @staticmethod
            def fromisoformat(value: str):
                return original_datetime.fromisoformat(value)

            @staticmethod
            def now(tz=None):
                return original_datetime(2026, 4, 11, 12, 12, 34, tzinfo=tz)

        native_shell_app.datetime = FixedDateTime
        try:
            app.refresh_dashboard_live_status_line()
        finally:
            native_shell_app.datetime = original_datetime

        self.assertEqual(uptime_widget.label, "⏱ 12:34")
        self.assertTrue(uptime_widget.visible)
        self.assertEqual(traffic_widget.label, "Скорость: 43.1 KB/s ↓ · 1.7 KB/s ↑\nОбъём: 5.2 GB ↓ · 432.9 MB ↑")
        self.assertTrue(meta_box.visible)

    def test_format_connection_duration_keeps_time_for_days(self) -> None:
        app = self.make_app()
        original_datetime = native_shell_app.datetime

        class FixedDateTime:
            @staticmethod
            def fromisoformat(value: str):
                return original_datetime.fromisoformat(value)

            @staticmethod
            def now(tz=None):
                return original_datetime(2026, 4, 11, 15, 7, 41, tzinfo=tz)

        native_shell_app.datetime = FixedDateTime
        try:
            formatted = app.format_connection_duration("2026-04-10T10:00:00")
        finally:
            native_shell_app.datetime = original_datetime

        self.assertEqual(formatted, "1д 5:07:41")

    def test_format_connection_duration_keeps_time_for_weeks_and_years(self) -> None:
        app = self.make_app()
        original_datetime = native_shell_app.datetime

        class FixedDateTime:
            @staticmethod
            def fromisoformat(value: str):
                return original_datetime.fromisoformat(value)

            @staticmethod
            def now(tz=None):
                return original_datetime(2026, 4, 11, 17, 7, 40, tzinfo=tz)

        native_shell_app.datetime = FixedDateTime
        try:
            weeks_formatted = app.format_connection_duration("2026-03-25T12:00:00")
            years_formatted = app.format_connection_duration("2025-02-10T12:00:00")
        finally:
            native_shell_app.datetime = original_datetime

        self.assertEqual(weeks_formatted, "2нед 3д 5:07:40")
        self.assertEqual(years_formatted, "1г 2мес 5:07:40")

    def test_refresh_dashboard_live_status_line_keeps_traffic_for_foreign_connection(self) -> None:
        app = self.make_app()
        uptime_widget = FakeButton()
        traffic_widget = FakeButton()
        meta_box = FakeButton()
        app.dashboard_labels = {
            "hero_uptime": uptime_widget,
            "hero_traffic": traffic_widget,
        }
        app.dashboard_status_meta_box = meta_box
        app.last_status_payload = {
            "summary": {"state": "degraded"},
            "runtime": {
                "ownership": "foreign",
                "connected_since": "2026-04-11T12:00:00",
            },
            "processes": {"xray_alive": True, "tun_present": True},
            "traffic": {
                "rx_rate_label": "43.1 KB/s",
                "tx_rate_label": "1.7 KB/s",
                "rx_total_label": "5.2 GB",
                "tx_total_label": "432.9 MB",
            },
        }

        original_datetime = native_shell_app.datetime

        class FixedDateTime:
            @staticmethod
            def fromisoformat(value: str):
                return original_datetime.fromisoformat(value)

            @staticmethod
            def now(tz=None):
                return original_datetime(2026, 4, 11, 12, 12, 34, tzinfo=tz)

        native_shell_app.datetime = FixedDateTime
        try:
            app.refresh_dashboard_live_status_line()
        finally:
            native_shell_app.datetime = original_datetime

        self.assertEqual(uptime_widget.label, "⏱ 12:34")
        self.assertTrue(uptime_widget.visible)
        self.assertEqual(traffic_widget.label, "Скорость: 43.1 KB/s ↓ · 1.7 KB/s ↑\nОбъём: 5.2 GB ↓ · 432.9 MB ↑")
        self.assertTrue(traffic_widget.visible)
        self.assertTrue(meta_box.visible)

    def test_show_page_switches_stack_child(self) -> None:
        class FakeStack:
            def __init__(self) -> None:
                self.page_id = None

            def set_visible_child_name(self, page_id: str) -> None:
                self.page_id = page_id

        app = self.make_app()
        app.stack = FakeStack()

        app.show_page("log")

        self.assertEqual(app.stack.page_id, "log")

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
        self.assertIn("=== Оболочка интерфейса (0) ===", rendered)
        self.assertIn("=== Подключение и служебный журнал (1) ===", rendered)
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
