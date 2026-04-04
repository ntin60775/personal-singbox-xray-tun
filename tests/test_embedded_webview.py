from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import embedded_webview  # noqa: E402


class EmbeddedWebViewTests(unittest.TestCase):
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
        width, height = embedded_webview.compute_startup_window_size(1440, 960, 1920, 1080)
        self.assertEqual(width, 1440)
        self.assertEqual(height, 1024)

    def test_compute_startup_window_size_caps_width_on_small_monitor(self) -> None:
        width, height = embedded_webview.compute_startup_window_size(1440, 960, 1280, 900)
        self.assertEqual(width, 1224)
        self.assertEqual(height, 844)


if __name__ == "__main__":
    unittest.main()
