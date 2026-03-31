from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import (  # noqa: E402
    MANUAL_PROFILE_ID,
    add_subscription,
    ensure_store_initialized,
    refresh_subscription,
    save_manual_import_results,
    save_store,
    sync_generated_runtime,
    update_profile,
)


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


class SubvostStoreTests(unittest.TestCase):
    def test_store_initialization_migrates_live_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))

            xray_config = {
                "outbounds": [
                    {
                        "tag": "proxy",
                        "protocol": "vless",
                        "settings": {
                            "vnext": [
                                {
                                    "address": "edge.example.com",
                                    "port": 443,
                                    "users": [{"id": "live-uuid", "encryption": "none"}],
                                }
                            ]
                        },
                        "streamSettings": {
                            "network": "xhttp",
                            "security": "reality",
                            "realitySettings": {
                                "serverName": "edge.example.com",
                                "fingerprint": "chrome",
                                "publicKey": "live-public",
                                "shortId": "live-short",
                                "spiderX": "/",
                            },
                            "xhttpSettings": {"host": "edge.example.com", "path": "/", "mode": "auto"},
                        },
                    }
                ]
            }
            (project_root / "xray-tun-subvost.json").write_text(json.dumps(xray_config), encoding="utf-8")

            store = ensure_store_initialized(paths, project_root)
            manual_profile = next(profile for profile in store["profiles"] if profile["id"] == MANUAL_PROFILE_ID)
            self.assertEqual(len(manual_profile["nodes"]), 1)
            self.assertEqual(store["active_selection"]["profile_id"], MANUAL_PROFILE_ID)
            self.assertTrue(paths.generated_xray_config_file.exists())

    def test_manual_import_can_activate_single_node(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(
                json.dumps(
                    {
                        "outbounds": [
                            {
                                "tag": "proxy",
                                "protocol": "vless",
                                "settings": {"vnext": [{"address": "template", "port": 443, "users": [{"id": "REPLACE_WITH_REALITY_UUID", "encryption": "none"}]}]},
                                "streamSettings": {
                                    "network": "xhttp",
                                    "security": "reality",
                                    "realitySettings": {
                                        "serverName": "template.example.com",
                                        "fingerprint": "chrome",
                                        "publicKey": "REPLACE_WITH_REALITY_PUBLIC_KEY",
                                        "shortId": "REPLACE_WITH_REALITY_SHORT_ID",
                                        "spiderX": "/",
                                    },
                                    "xhttpSettings": {"host": "template.example.com", "path": "/", "mode": "auto"},
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            store = ensure_store_initialized(paths, project_root)
            previews = [
                {
                    "valid": True,
                    "raw_uri": "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node",
                    "fingerprint": "fingerprint-1",
                    "normalized": {
                        "fingerprint_hash": "fingerprint-1",
                        "protocol": "vless",
                        "address": "example.com",
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
                        "display_name": "Node",
                        "raw_uri": "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node",
                    },
                }
            ]
            save_manual_import_results(store, previews, activate_single=True)
            save_store(paths, store)
            sync_generated_runtime(store, paths, project_root)
            self.assertEqual(store["active_selection"]["profile_id"], MANUAL_PROFILE_ID)
            self.assertTrue(paths.generated_xray_config_file.exists())

    def test_refresh_subscription_preserves_user_renamed_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")
            save_store(paths, store)

            payload = (
                b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Imported\n"
            )
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])

            profile = next(profile for profile in store["profiles"] if profile["id"] == subscription["profile_id"])
            profile["nodes"][0]["name"] = "Custom name"
            profile["nodes"][0]["user_renamed"] = True

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-2"})):
                refresh_subscription(store, subscription["id"])

            self.assertEqual(profile["nodes"][0]["name"], "Custom name")
            self.assertEqual(store["subscriptions"][0]["etag"], "etag-2")

    def test_refresh_subscription_deduplicates_duplicate_lines_within_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            payload = (
                b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Imported\n"
                b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Imported\n"
            )
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])

            profile = next(profile for profile in store["profiles"] if profile["id"] == subscription["profile_id"])
            self.assertEqual(len(profile["nodes"]), 1)

    def test_refresh_subscription_preserves_profile_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            payload = (
                b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Imported\n"
            )
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])

            profile = update_profile(store, subscription["profile_id"], name="Custom profile", enabled=False)
            self.assertEqual(profile["name"], "Custom profile")
            self.assertFalse(profile["enabled"])
            self.assertEqual(store["subscriptions"][0]["name"], "Custom profile")
            self.assertFalse(store["subscriptions"][0]["enabled"])

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-2"})):
                refresh_subscription(store, subscription["id"])

            self.assertEqual(profile["name"], "Custom profile")
            self.assertFalse(profile["enabled"])
            self.assertEqual(store["subscriptions"][0]["etag"], "etag-2")


if __name__ == "__main__":
    unittest.main()
