from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import gui_server  # noqa: E402
from subvost_paths import build_app_paths  # noqa: E402


class GuiServerRuntimeSelectionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
