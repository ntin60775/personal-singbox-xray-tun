from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import windows_core_cli  # noqa: E402
from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import ensure_store_initialized, save_store  # noqa: E402


def template_config() -> dict[str, object]:
    return {
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": "template.example.com",
                            "port": 443,
                            "users": [{"id": "00000000-0000-0000-0000-000000000000", "encryption": "none"}],
                        }
                    ]
                },
                "streamSettings": {"network": "tcp", "security": "none"},
            },
            {"tag": "direct", "protocol": "freedom"},
        ]
    }


def node_record() -> dict[str, object]:
    return {
        "id": "node-1",
        "name": "Финляндия",
        "enabled": True,
        "parse_error": "",
        "protocol": "vless",
        "origin": {"kind": "manual"},
        "normalized": {
            "fingerprint_hash": "node-1",
            "protocol": "vless",
            "address": "edge.example.com",
            "port": 443,
            "uuid": "11111111-1111-1111-1111-111111111111",
            "encryption": "none",
            "flow": "",
            "network": "tcp",
            "security": "none",
            "host": "",
            "path": "",
            "server_name": "",
            "service_name": "",
            "grpc_authority": "",
            "fingerprint": "",
            "public_key": "",
            "short_id": "",
            "spider_x": "/",
            "mode": "auto",
            "alpn": [],
            "allow_insecure": False,
            "display_name": "Финляндия",
            "raw_uri": "vless://11111111-1111-1111-1111-111111111111@edge.example.com:443?type=tcp&security=none#Finland",
        },
    }


class WindowsCoreHelperContractTests(unittest.TestCase):
    def run_cli(self, root: Path, home: Path, local_app_data: Path, args: list[str]) -> tuple[int, dict[str, object]]:
        env = {
            "SUBVOST_PROJECT_ROOT": str(root),
            "SUBVOST_WINDOWS_HOME": str(home),
            "SUBVOST_WINDOWS_LOCALAPPDATA": str(local_app_data),
        }
        stdout = io.StringIO()
        with patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(stdout):
            code = windows_core_cli.main(args)
        return code, json.loads(stdout.getvalue())

    def make_project(self, temp_dir: str) -> tuple[Path, Path, Path]:
        root = Path(temp_dir) / "project"
        home = Path(temp_dir) / "home"
        local_app_data = home / "AppData" / "Local"
        root.mkdir()
        home.mkdir()
        local_app_data.mkdir(parents=True)
        (root / "xray-tun-subvost.json").write_text(json.dumps(template_config()), encoding="utf-8")
        return root, home, local_app_data

    def test_status_returns_stable_json_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, home, local_app_data = self.make_project(temp_dir)

            code, payload = self.run_cli(root, home, local_app_data, ["status", "--json"])

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "status")
        self.assertIn("Подключение", payload["message"])
        self.assertIn("status", payload)
        self.assertIn("store", payload)
        self.assertIsNone(payload["error"])

    def test_runtime_start_error_is_json_with_russian_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, home, local_app_data = self.make_project(temp_dir)

            code, payload = self.run_cli(root, home, local_app_data, ["runtime", "start", "--json"])

        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("Нет активного валидного узла", payload["message"])
        self.assertEqual(payload["error"]["type"], "CommandError")

    def test_subscription_add_without_refresh_updates_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, home, local_app_data = self.make_project(temp_dir)

            code, payload = self.run_cli(
                root,
                home,
                local_app_data,
                ["subscriptions", "add", "--name", "Тест", "--url", "https://example.com/sub", "--no-refresh", "--json"],
            )

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["subscription"]["name"], "Тест")
        self.assertEqual(payload["store"]["summary"]["subscriptions_total"], 1)

    def test_nodes_activate_materializes_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, home, local_app_data = self.make_project(temp_dir)
            paths = build_app_paths(home, str(local_app_data))
            store = ensure_store_initialized(paths, root)
            store["profiles"][0]["nodes"].append(node_record())
            save_store(paths, store)

            code, payload = self.run_cli(
                root,
                home,
                local_app_data,
                ["nodes", "activate", "--profile-id", "manual", "--node-id", "node-1", "--json"],
            )
            config_exists = Path(payload["status"]["runtime"]["active_xray_config"]).exists()

        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"]["connection"]["active_name"], "Финляндия")
        self.assertTrue(config_exists)


if __name__ == "__main__":
    unittest.main()
