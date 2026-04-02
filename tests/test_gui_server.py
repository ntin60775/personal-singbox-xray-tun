from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import gui_server  # noqa: E402
from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import add_subscription, ensure_store_initialized, refresh_subscription, save_store  # noqa: E402


class FakeResponse:
    def __init__(self, payload: bytes, headers: dict[str, str] | None = None, status: int = 200) -> None:
        self._payload = payload
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class GuiServerRuntimeSelectionTests(unittest.TestCase):
    def test_index_html_normalizes_data_attribute_names_for_dataset_actions(self) -> None:
        self.assertIn("function normalizeDataAttrName(name)", gui_server.INDEX_HTML)
        self.assertIn('data-${normalizeDataAttrName(key)}="${escapeAttr(value)}"', gui_server.INDEX_HTML)
        self.assertNotIn('data-${key}="${escapeAttr(value)}"', gui_server.INDEX_HTML)

    def test_design_review_asset_contains_clash_fullscreen_candidate(self) -> None:
        self.assertEqual(gui_server.MAIN_GUI_ASSET, "design_review.html")
        html = gui_server.load_gui_asset(gui_server.MAIN_GUI_ASSET)
        self.assertIn('id="clash-candidate"', html)
        self.assertIn("Главная панель", html)
        self.assertIn('fetch("/api/store"', html)

    def test_legacy_routes_are_defined_for_old_embedded_ui(self) -> None:
        self.assertIn("/legacy-ui", gui_server.LEGACY_GUI_PATHS)
        self.assertIn("/classic-ui", gui_server.LEGACY_GUI_PATHS)

    def test_resolve_active_xray_config_prefers_snapshot_only_for_live_stack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            template = root / "xray-tun-subvost.json"
            template.write_text("{}", encoding="utf-8")
            paths.generated_xray_config_file.write_text('{"generated": true}', encoding="utf-8")
            paths.active_runtime_xray_config_file.write_text('{"snapshot": true}', encoding="utf-8")

            store = {"active_selection": {"profile_id": "profile-1", "node_id": "node-1"}}
            state = {"XRAY_CONFIG": str(paths.active_runtime_xray_config_file)}

            with patch.object(gui_server, "APP_PATHS", paths), patch.object(gui_server, "XRAY_TEMPLATE_PATH", template):
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path(store, state, stack_is_live=True),
                    paths.active_runtime_xray_config_file,
                )
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path(store, state, stack_is_live=False),
                    paths.generated_xray_config_file,
                )

    def test_resolve_active_xray_config_respects_builtin_preference_when_stack_is_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            template = root / "xray-tun-subvost.json"
            template.write_text('{"builtin": true}', encoding="utf-8")
            paths.generated_xray_config_file.write_text('{"generated": true}', encoding="utf-8")

            store = {
                "runtime_preference": "builtin",
                "active_selection": {"profile_id": "profile-1", "node_id": "node-1"},
            }

            with patch.object(gui_server, "APP_PATHS", paths), patch.object(gui_server, "XRAY_TEMPLATE_PATH", template):
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path(store, {}, stack_is_live=False),
                    template,
                )

    def test_resolve_active_xray_config_falls_back_to_template_without_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            template = root / "xray-tun-subvost.json"
            template.write_text("{}", encoding="utf-8")

            with patch.object(gui_server, "APP_PATHS", paths), patch.object(gui_server, "XRAY_TEMPLATE_PATH", template):
                resolved = gui_server.resolve_active_xray_config_path(
                    {"active_selection": {"profile_id": None, "node_id": None}},
                    {"XRAY_CONFIG": str(paths.active_runtime_xray_config_file)},
                    stack_is_live=False,
                )
                self.assertEqual(resolved, template)


class GuiServerSubscriptionRollbackTests(unittest.TestCase):
    def test_handle_subscription_refresh_persists_last_error_and_builtin_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")

            store = ensure_store_initialized(paths, root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")
            valid_payload = b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Stable\n"
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(valid_payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])
            save_store(paths, store)

            invalid_payload = base64.urlsafe_b64encode(
                (
                    "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Changed\n"
                    "vless://broken\n"
                ).encode("utf-8")
            )
            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "XRAY_TEMPLATE_PATH", template),
                patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(invalid_payload, {"ETag": "etag-2"})),
            ):
                with self.assertRaisesRegex(ValueError, "Сохранена предыдущая версия"):
                    gui_server.handle_subscription_refresh({"subscription_id": subscription["id"]})

            persisted = json.loads(paths.store_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["runtime_preference"], "builtin")
            self.assertEqual(persisted["subscriptions"][0]["last_status"], "error")
            self.assertIn("невалидных строк 1", persisted["subscriptions"][0]["last_error"])
            self.assertEqual(len(persisted["profiles"][1]["nodes"]), 1)
            self.assertIn("#Stable", persisted["profiles"][1]["nodes"][0]["raw_uri"])

    def test_handle_subscription_add_rolls_back_failed_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            ensure_store_initialized(paths, root)

            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "XRAY_TEMPLATE_PATH", template),
                patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(b"bad-link\n")),
            ):
                with self.assertRaisesRegex(ValueError, "Подписка не добавлена"):
                    gui_server.handle_subscription_add({"name": "Broken", "url": "https://example.com/sub"})

            persisted = json.loads(paths.store_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["runtime_preference"], "builtin")
            self.assertEqual(persisted["subscriptions"], [])
            self.assertEqual(len(persisted["profiles"]), 1)


if __name__ == "__main__":
    unittest.main()
