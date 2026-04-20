from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from native_shell_shared import (  # noqa: E402
    NativeShellSettings,
    active_routing_profile_from_store_snapshot,
    build_native_shell_log_text,
    build_startup_notes,
    build_tray_support,
    filter_log_entries,
    latest_error_from_log_entries,
    log_entries_from_status,
    native_shell_theme_label,
    native_shell_action_label,
    native_shell_log_filter_label,
    normalize_native_shell_theme,
    ping_snapshot_from_status,
    resolve_selected_subscription_id,
    selected_profile_from_store_snapshot,
    selected_subscription_from_store_snapshot,
    select_indicator_candidate,
    select_status_notifier_watcher,
    should_hide_on_close,
    should_start_hidden,
    tray_action_label,
)


class NativeShellSharedTests(unittest.TestCase):
    def test_settings_from_mapping_normalizes_unknown_theme(self) -> None:
        settings = NativeShellSettings.from_mapping(
            {
                "file_logs_enabled": 1,
                "close_to_tray": "yes",
                "start_minimized_to_tray": 0,
                "theme": "sepia",
            }
        )

        self.assertTrue(settings.file_logs_enabled)
        self.assertTrue(settings.close_to_tray)
        self.assertFalse(settings.start_minimized_to_tray)
        self.assertEqual(settings.theme, "dark")
        self.assertEqual(settings.artifact_retention_days, 7)

    def test_select_indicator_candidate_prefers_ayatana(self) -> None:
        candidate = select_indicator_candidate(
            {
                "AyatanaAppIndicator3": {"0.1"},
                "AppIndicator3": {"0.1"},
            }
        )

        self.assertEqual(candidate, ("AyatanaAppIndicator3", "0.1", "Ayatana AppIndicator"))

    def test_select_status_notifier_watcher_returns_known_name(self) -> None:
        watcher = select_status_notifier_watcher({"org.example.Other", "org.kde.StatusNotifierWatcher"})
        self.assertEqual(watcher, "org.kde.StatusNotifierWatcher")

    def test_build_tray_support_reports_fallback_when_watcher_missing(self) -> None:
        tray_support = build_tray_support(
            watcher_name=None,
            indicator_candidate=("AyatanaAppIndicator3", "0.1", "Ayatana AppIndicator"),
        )

        self.assertFalse(tray_support.available)
        self.assertIn("status notifier watcher", tray_support.reason)

    def test_close_and_start_hidden_require_working_tray(self) -> None:
        settings = NativeShellSettings(close_to_tray=True, start_minimized_to_tray=True)
        tray_support = build_tray_support(
            watcher_name="org.kde.StatusNotifierWatcher",
            indicator_candidate=("AyatanaAppIndicator3", "0.1", "Ayatana AppIndicator"),
        )
        fallback = build_tray_support(watcher_name=None, indicator_candidate=None)

        self.assertTrue(should_hide_on_close(settings, tray_support))
        self.assertTrue(should_start_hidden(settings, tray_support))
        self.assertFalse(should_hide_on_close(settings, fallback))
        self.assertFalse(should_start_hidden(settings, fallback))

    def test_build_startup_notes_explain_fallback_for_saved_tray_prefs(self) -> None:
        settings = NativeShellSettings(close_to_tray=True, start_minimized_to_tray=True, theme="dark")
        notes = build_startup_notes(settings, build_tray_support(watcher_name=None, indicator_candidate=None))

        self.assertIn("Тема: Тёмная.", notes)
        self.assertTrue(any("окно откроется обычно" in item for item in notes))
        self.assertTrue(any("окно будет закрываться полностью" in item for item in notes))

    def test_theme_label_and_action_label_use_known_mappings(self) -> None:
        self.assertEqual(normalize_native_shell_theme(" DARK "), "dark")
        self.assertEqual(normalize_native_shell_theme("light"), "dark")
        self.assertEqual(normalize_native_shell_theme("system"), "dark")
        self.assertEqual(native_shell_theme_label("dark"), "Тёмная")
        self.assertEqual(tray_action_label("capture-diagnostics"), "Снять диагностику")
        self.assertEqual(native_shell_action_label("subscription-refresh"), "Обновление подписки")

    def test_resolve_selected_subscription_id_prefers_current_then_active_then_first(self) -> None:
        store_payload = {
            "store": {
                "subscriptions": [
                    {"id": "sub-1", "profile_id": "profile-1"},
                    {"id": "sub-2", "profile_id": "profile-2"},
                ],
                "profiles": [],
                "routing": {},
            },
            "active_profile": {"id": "profile-2", "source_subscription_id": "sub-2"},
        }

        self.assertEqual(resolve_selected_subscription_id(store_payload, "sub-1"), "sub-1")
        self.assertEqual(resolve_selected_subscription_id(store_payload, "missing"), "sub-2")
        self.assertEqual(resolve_selected_subscription_id({"store": {"subscriptions": [{"id": "sub-3"}]}}, None), "sub-3")

    def test_selected_snapshot_helpers_return_subscription_profile_and_routing(self) -> None:
        store_payload = {
            "store": {
                "subscriptions": [
                    {"id": "sub-1", "profile_id": "profile-1"},
                ],
                "profiles": [
                    {"id": "profile-1", "nodes": [{"id": "node-1"}]},
                ],
                "routing": {
                    "profiles": [{"id": "routing-1"}],
                },
            },
            "active_profile": {"id": "profile-1", "source_subscription_id": "sub-1"},
            "active_routing_profile": {"id": "routing-1", "name": "RU"},
        }

        self.assertEqual(selected_subscription_from_store_snapshot(store_payload, None), {"id": "sub-1", "profile_id": "profile-1"})
        self.assertEqual(selected_profile_from_store_snapshot(store_payload, None), {"id": "profile-1", "nodes": [{"id": "node-1"}]})
        self.assertEqual(active_routing_profile_from_store_snapshot(store_payload), {"id": "routing-1", "name": "RU"})

    def test_ping_snapshot_is_read_from_status_cache(self) -> None:
        status_payload = {
            "ping": {
                "cache": {
                    "profile-1:node-1": {"label": "12.4 мс", "ok": True},
                }
            }
        }

        self.assertEqual(
            ping_snapshot_from_status(status_payload, "profile-1", "node-1"),
            {"label": "12.4 мс", "ok": True},
        )
        self.assertIsNone(ping_snapshot_from_status(status_payload, "profile-1", "missing"))

    def test_log_helpers_filter_and_render_sections(self) -> None:
        bundle_entries = [
            {
                "timestamp": "2026-04-10T10:00:00",
                "name": "Старт",
                "level": "info",
                "message": "Runtime запущен.",
                "details": "",
                "source": "action",
            },
            {
                "timestamp": None,
                "name": "xray",
                "level": "error",
                "message": "failed to resolve host",
                "details": "traceback line",
                "source": "file",
            },
        ]
        shell_entries = [
            {
                "timestamp": "2026-04-10T10:01:00",
                "name": "tray",
                "level": "warning",
                "message": "Tray helper завершился.",
                "details": "",
                "source": "shell",
            }
        ]

        rendered = build_native_shell_log_text(
            bundle_entries=bundle_entries,
            shell_entries=shell_entries,
            level_filter="warning",
        )

        self.assertEqual(native_shell_log_filter_label("warning"), "Предупреждения")
        self.assertEqual(filter_log_entries(bundle_entries, "error"), [bundle_entries[1]])
        self.assertIn("=== Оболочка интерфейса (1) ===", rendered)
        self.assertIn("=== Подключение и служебный журнал (0) ===", rendered)
        self.assertIn("Tray helper завершился.", rendered)

    def test_log_helpers_pick_latest_error_and_read_entries_from_status(self) -> None:
        status_payload = {
            "logs": {
                "entries": [
                    {"timestamp": None, "level": "error", "message": "runtime error", "source": "file"},
                    {"timestamp": "2026-04-10T10:02:00", "level": "error", "message": "shell error", "source": "shell"},
                ]
            }
        }

        entries = log_entries_from_status(status_payload)

        self.assertEqual(len(entries), 2)
        self.assertEqual(latest_error_from_log_entries(entries)["message"], "shell error")


if __name__ == "__main__":
    unittest.main()
