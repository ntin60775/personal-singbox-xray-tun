from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from native_shell_shared import (  # noqa: E402
    NativeShellSettings,
    build_startup_notes,
    build_tray_support,
    native_shell_theme_label,
    normalize_native_shell_theme,
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
        self.assertEqual(settings.theme, "system")

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

        self.assertIn("Theme: Тёмная.", notes)
        self.assertTrue(any("окно откроется обычно" in item for item in notes))
        self.assertTrue(any("окно будет закрываться полностью" in item for item in notes))

    def test_theme_label_and_action_label_use_known_mappings(self) -> None:
        self.assertEqual(normalize_native_shell_theme(" DARK "), "dark")
        self.assertEqual(native_shell_theme_label("dark"), "Тёмная")
        self.assertEqual(tray_action_label("capture-diagnostics"), "Снять диагностику")


if __name__ == "__main__":
    unittest.main()
