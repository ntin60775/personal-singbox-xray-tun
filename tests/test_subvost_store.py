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

from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import (  # noqa: E402
    MANUAL_PROFILE_ID,
    add_subscription,
    default_subscription_hwid,
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
    def test_default_subscription_hwid_prefers_real_home_from_env(self) -> None:
        with patch.dict("os.environ", {"SUBVOST_REAL_HOME": "/tmp/subvost-real-home"}, clear=False):
            first = default_subscription_hwid()
        with patch.dict("os.environ", {"SUBVOST_REAL_HOME": "/tmp/subvost-real-home"}, clear=False):
            second = default_subscription_hwid()
        with patch.dict("os.environ", {"SUBVOST_REAL_HOME": "/tmp/another-home"}, clear=False):
            third = default_subscription_hwid()

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_store_initialization_does_not_migrate_tracked_config(self) -> None:
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
            self.assertEqual(len(manual_profile["nodes"]), 0)
            self.assertIsNone(store["active_selection"]["profile_id"])
            self.assertFalse(paths.generated_xray_config_file.exists())

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
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-1"})) as mocked_urlopen:
                result = refresh_subscription(store, subscription["id"])
            self.assertEqual(result["unique_nodes"], 1)
            self.assertEqual(result["duplicate_lines"], 0)
            request = mocked_urlopen.call_args.args[0]
            self.assertEqual(request.get_header("User-agent"), "Xray-core")
            self.assertTrue(request.get_header("X-hwid"))

            profile = next(profile for profile in store["profiles"] if profile["id"] == subscription["profile_id"])
            profile["nodes"][0]["name"] = "Custom name"
            profile["nodes"][0]["user_renamed"] = True

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(payload, {"ETag": "etag-2"})):
                refresh_subscription(store, subscription["id"])

            self.assertEqual(profile["nodes"][0]["name"], "Custom name")
            self.assertEqual(store["subscriptions"][0]["etag"], "etag-2")

    def test_refresh_subscription_does_not_auto_activate_first_node(self) -> None:
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

            self.assertIsNone(store["active_selection"]["profile_id"])
            self.assertIsNone(store["active_selection"]["node_id"])

    def test_refresh_subscription_rejects_provider_placeholder_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Stub", "https://example.com/sub")

            stub_payload = base64.urlsafe_b64encode(
                (
                    "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?type=tcp&security=none#Приложение не поддерживаетя\n"
                    "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?type=tcp&security=none#Обратись к @provider_support\n"
                ).encode("utf-8")
            )

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(stub_payload, {"ETag": "etag-1"})):
                with self.assertRaisesRegex(ValueError, "заглушку"):
                    refresh_subscription(store, subscription["id"])

            self.assertEqual(store["subscriptions"][0]["last_status"], "error")
            self.assertIn("заглушку", store["subscriptions"][0]["last_error"])

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
                result = refresh_subscription(store, subscription["id"])

            profile = next(profile for profile in store["profiles"] if profile["id"] == subscription["profile_id"])
            self.assertEqual(len(profile["nodes"]), 1)
            self.assertEqual(result["valid"], 2)
            self.assertEqual(result["unique_nodes"], 1)
            self.assertEqual(result["duplicate_lines"], 1)

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

    def test_refresh_subscription_is_atomic_when_payload_contains_invalid_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Atomic", "https://example.com/sub")

            valid_payload = (
                b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Stable\n"
            )
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(valid_payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])

            profile = next(profile for profile in store["profiles"] if profile["id"] == subscription["profile_id"])
            original_node = json.loads(json.dumps(profile["nodes"][0], ensure_ascii=False))

            invalid_payload = base64.urlsafe_b64encode(
                (
                    "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Updated\n"
                    "vless://broken\n"
                ).encode("utf-8")
            )
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(invalid_payload, {"ETag": "etag-2"})):
                with self.assertRaisesRegex(ValueError, "Обновление подписки не применено"):
                    refresh_subscription(store, subscription["id"])

            self.assertEqual(profile["nodes"][0]["name"], original_node["name"])
            self.assertEqual(profile["nodes"][0]["raw_uri"], original_node["raw_uri"])
            self.assertEqual(store["subscriptions"][0]["etag"], "etag-1")
            self.assertEqual(store["subscriptions"][0]["last_status"], "error")
            self.assertIn("невалидных строк 1", store["subscriptions"][0]["last_error"])

if __name__ == "__main__":
    unittest.main()
