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
    activate_routing_profile,
    add_subscription,
    default_subscription_hwid,
    delete_subscription,
    ensure_store_structure,
    ensure_store_initialized,
    import_routing_profile,
    read_gui_settings,
    refresh_subscription,
    save_gui_settings,
    save_manual_import_results,
    save_store,
    set_routing_enabled,
    sync_generated_runtime,
    update_routing_profile_enabled,
    update_profile,
)


def happ_routing_uri(payload: dict[str, object], *, mode: str = "add") -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return f"happ://routing/{mode}/{encoded}"


def single_vless_line(name: str = "Node") -> bytes:
    return (
        f"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#{name}\n"
    ).encode("utf-8")



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
    def test_save_gui_settings_preserves_native_shell_fields_on_partial_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            real_home = Path(temp_dir) / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))

            save_gui_settings(
                paths,
                True,
                close_to_tray=True,
                start_minimized_to_tray=True,
                theme="dark",
            )
            save_gui_settings(paths, False)

            settings = read_gui_settings(paths)
            self.assertEqual(
                settings,
                {
                    "file_logs_enabled": False,
                    "close_to_tray": True,
                    "start_minimized_to_tray": True,
                    "theme": "dark",
                    "artifact_retention_days": 7,
                },
            )

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

    def test_routing_profile_import_and_enable_generates_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(
                json.dumps(
                    {
                        "outbounds": [
                            {"tag": "proxy", "protocol": "vless", "settings": {"vnext": [{"address": "template", "port": 443, "users": [{"id": "uuid", "encryption": "none"}]}]}, "streamSettings": {"network": "tcp", "security": "none"}},
                            {"tag": "direct", "protocol": "freedom"},
                            {"tag": "block", "protocol": "blackhole"},
                        ],
                        "routing": {
                            "domainStrategy": "AsIs",
                            "rules": [
                                {"type": "field", "inboundTag": ["tun-in"], "port": "53", "outboundTag": "dns-out"},
                                {"type": "field", "inboundTag": ["tun-in"], "network": "tcp,udp", "outboundTag": "proxy"},
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            store = ensure_store_initialized(paths, project_root)
            manual_profile = next(profile for profile in store["profiles"] if profile["id"] == MANUAL_PROFILE_ID)
            manual_profile["nodes"].append(
                {
                    "id": "node-1",
                    "fingerprint": "fingerprint-1",
                    "name": "Node-1",
                    "protocol": "vless",
                    "raw_uri": "vless://...",
                    "origin": {"kind": "manual", "subscription_id": None},
                    "enabled": True,
                    "user_renamed": False,
                    "parse_error": "",
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
                        "xhttp_extra": {},
                        "alpn": [],
                        "allow_insecure": False,
                        "display_name": "Node-1",
                        "raw_uri": "vless://...",
                    },
                    "created_at": "2026-04-08T00:00:00+00:00",
                    "updated_at": "2026-04-08T00:00:00+00:00",
                }
            )
            store["active_selection"] = {
                "profile_id": MANUAL_PROFILE_ID,
                "node_id": "node-1",
                "activated_at": "2026-04-08T00:00:00+00:00",
                "source": "test",
            }

            routing_json = json.dumps(
                {
                    "name": "SubVostVPN",
                    "globalproxy": False,
                    "domainstrategy": "IPIfNonMatch",
                    "directsites": ["geosite:private"],
                    "directip": ["geoip:private"],
                    "proxysites": ["geosite:youtube"],
                    "proxyip": [],
                    "blocksites": ["geosite:category-ads"],
                    "blockip": [],
                    "geoipurl": "https://example.com/geoip.dat",
                    "geositeurl": "https://example.com/geosite.dat",
                }
            )

            with patch(
                "subvost_routing.urllib.request.urlopen",
                side_effect=[FakeResponse(b"geoip"), FakeResponse(b"geosite")],
            ):
                result = import_routing_profile(store, paths, routing_json)
                activate_routing_profile(store, paths, result["profile"]["id"])
                set_routing_enabled(store, paths, True)

            sync_generated_runtime(store, paths, project_root)
            rendered = json.loads(paths.generated_xray_config_file.read_text(encoding="utf-8"))

            self.assertTrue(store["routing"]["enabled"])
            self.assertTrue(store["routing"]["geodata"]["ready"])
            self.assertEqual(rendered["routing"]["domainStrategy"], "IPIfNonMatch")
            self.assertEqual(rendered["routing"]["rules"][-1]["outboundTag"], "direct")

    def test_disabling_active_routing_profile_clears_master_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = build_app_paths(Path(temp_dir) / "home", str(Path(temp_dir) / "home" / ".config"))
            (Path(temp_dir) / "home").mkdir()
            store = ensure_store_structure({})
            store["routing"]["profiles"].append(
                {
                    "id": "routing-1",
                    "name": "SubVostVPN",
                    "name_key": "subvostvpn",
                    "enabled": True,
                    "source_format": "json",
                    "raw_payload": {"name": "SubVostVPN"},
                    "global_proxy": True,
                    "domain_strategy": "AsIs",
                    "geoip_url": "https://example.com/geoip.dat",
                    "geosite_url": "https://example.com/geosite.dat",
                    "direct_sites": [],
                    "direct_ip": [],
                    "proxy_sites": [],
                    "proxy_ip": [],
                    "block_sites": [],
                    "block_ip": [],
                    "dns_hosts": {},
                    "domestic_dns_domain": "",
                    "domestic_dns_ip": "",
                    "domestic_dns_type": "",
                    "remote_dns_domain": "",
                    "remote_dns_ip": "",
                    "remote_dns_type": "",
                    "fake_dns": False,
                    "route_order": ["block", "direct", "proxy"],
                    "last_updated": "",
                    "supported_entry_count": 0,
                    "stored_only_fields": [],
                    "ignored_fields": [],
                    "unknown_fields": [],
                    "created_at": "2026-04-08T00:00:00+00:00",
                    "updated_at": "2026-04-08T00:00:00+00:00",
                }
            )
            store["routing"]["active_profile_id"] = "routing-1"
            store["routing"]["enabled"] = True

            update_routing_profile_enabled(store, paths, "routing-1", enabled=False)

            self.assertFalse(store["routing"]["enabled"])
            self.assertIsNone(store["routing"]["active_profile_id"])

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

    def test_refresh_subscription_auto_imports_routing_profile_from_response_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            routing_uri = happ_routing_uri(
                {
                    "name": "Header route",
                    "directsites": ["geosite:cn"],
                    "directip": ["geoip:cn"],
                    "proxysites": ["geosite:youtube"],
                },
                mode="onadd",
            )
            headers = {"ETag": "etag-1", "routing": routing_uri, "providerid": "provider-header"}

            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(single_vless_line(), headers),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                ],
            ):
                result = refresh_subscription(store, subscription["id"], paths=paths)

            self.assertEqual(result["routing"]["status"], "created")
            self.assertEqual(result["routing"]["source"], "response_header")
            self.assertEqual(result["routing"]["provider_id"], "provider-header")
            self.assertTrue(result["routing"]["activated"])
            self.assertEqual(result["routing"]["geodata_status"], "ready")

            saved_subscription = store["subscriptions"][0]
            self.assertEqual(saved_subscription["provider_id"], "provider-header")
            self.assertEqual(saved_subscription["provider_id_source"], "response_header")
            self.assertEqual(saved_subscription["last_routing_status"], "linked")
            self.assertEqual(saved_subscription["last_routing_error"], "")

            profile = next(item for item in store["routing"]["profiles"] if item["id"] == saved_subscription["routing_profile_id"])
            self.assertTrue(profile["auto_managed"])
            self.assertEqual(profile["source_subscription_id"], subscription["id"])
            self.assertEqual(profile["provider_id"], "provider-header")
            self.assertEqual(profile["source_kind"], "response_header")
            self.assertEqual(profile["activation_mode"], "onadd")
            self.assertEqual(profile["direct_sites"], ["geosite:cn"])
            self.assertEqual(profile["direct_ip"], ["geoip:cn"])
            self.assertEqual(store["routing"]["active_profile_id"], profile["id"])
            self.assertTrue(store["routing"]["geodata"]["ready"])

    def test_refresh_subscription_auto_imports_routing_profile_from_mixed_base64_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            routing_uri = happ_routing_uri(
                {
                    "name": "Body route",
                    "directsites": ["geosite:private"],
                    "directip": ["geoip:private"],
                    "blocksites": ["geosite:category-ads"],
                },
                mode="onadd",
            )
            mixed_body = (
                "#profile-title Example\n"
                "#providerid provider-body\n"
                f"{routing_uri}\n"
                f"{single_vless_line().decode('utf-8')}"
            )
            payload = base64.urlsafe_b64encode(mixed_body.encode("utf-8"))

            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(payload, {"ETag": "etag-1"}),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                ],
            ):
                result = refresh_subscription(store, subscription["id"], paths=paths)

            self.assertEqual(result["format"], "base64")
            self.assertEqual(result["provider_id"], "provider-body")
            self.assertEqual(result["routing"]["status"], "created")
            self.assertEqual(result["routing"]["source"], "body_base64")
            self.assertEqual(store["subscriptions"][0]["provider_id_source"], "body_base64")

            profile = next(item for item in store["routing"]["profiles"] if item["id"] == store["subscriptions"][0]["routing_profile_id"])
            self.assertEqual(profile["name"], "Body route")
            self.assertEqual(profile["activation_mode"], "onadd")
            self.assertEqual(profile["direct_sites"], ["geosite:private"])
            self.assertEqual(profile["direct_ip"], ["geoip:private"])
            self.assertEqual(profile["block_sites"], ["geosite:category-ads"])

    def test_refresh_subscription_does_not_clobber_manual_routing_profile_with_same_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)

            with patch(
                "subvost_routing.urllib.request.urlopen",
                side_effect=[FakeResponse(b"geoip-bytes"), FakeResponse(b"geosite-bytes")],
            ):
                imported = import_routing_profile(
                    store,
                    paths,
                    json.dumps({"name": "Shared route", "directsites": ["geosite:private"], "directip": ["geoip:private"]}),
                )
            manual_profile_id = imported["profile"]["id"]
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            routing_uri = happ_routing_uri(
                {"name": "Shared route", "directsites": ["geosite:cn"], "directip": ["geoip:cn"]},
                mode="add",
            )
            headers = {"ETag": "etag-1", "routing": routing_uri, "providerid": "provider-auto"}

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(single_vless_line(), headers)):
                result = refresh_subscription(store, subscription["id"], paths=paths)

            same_name_profiles = [item for item in store["routing"]["profiles"] if item["name"] == "Shared route"]
            self.assertEqual(len(same_name_profiles), 2)
            manual_profile = next(item for item in same_name_profiles if not item.get("auto_managed"))
            auto_profile = next(item for item in same_name_profiles if item.get("auto_managed"))

            self.assertEqual(manual_profile["id"], manual_profile_id)
            self.assertEqual(manual_profile["direct_sites"], ["geosite:private"])
            self.assertEqual(manual_profile["direct_ip"], ["geoip:private"])
            self.assertEqual(auto_profile["source_subscription_id"], subscription["id"])
            self.assertEqual(auto_profile["provider_id"], "provider-auto")
            self.assertEqual(auto_profile["direct_sites"], ["geosite:cn"])
            self.assertEqual(auto_profile["direct_ip"], ["geoip:cn"])
            self.assertEqual(store["routing"]["active_profile_id"], manual_profile_id)
            self.assertFalse(result["routing"]["activated"])

    def test_delete_subscription_removes_linked_auto_managed_routing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            routing_uri = happ_routing_uri({"name": "Delete me", "directsites": ["geosite:cn"]}, mode="onadd")
            headers = {"ETag": "etag-1", "routing": routing_uri, "providerid": "provider-delete"}
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(single_vless_line(), headers),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                ],
            ):
                refresh_subscription(store, subscription["id"], paths=paths)

            delete_subscription(store, subscription["id"], paths=paths)

            self.assertEqual(store["subscriptions"], [])
            self.assertEqual([profile["id"] for profile in store["profiles"]], [MANUAL_PROFILE_ID])
            self.assertEqual(store["routing"]["profiles"], [])
            self.assertIsNone(store["routing"]["active_profile_id"])
            self.assertFalse(store["routing"]["enabled"])
            self.assertFalse(store["routing"]["runtime_ready"])

    def test_refresh_subscription_reads_provider_id_from_url_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub#?providerid=url-fragment")

            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(single_vless_line(), {"ETag": "etag-1"})):
                result = refresh_subscription(store, subscription["id"])

            self.assertEqual(result["provider_id"], "url-fragment")
            self.assertEqual(result["routing"]["status"], "none")
            self.assertEqual(store["subscriptions"][0]["provider_id"], "url-fragment")
            self.assertEqual(store["subscriptions"][0]["provider_id_source"], "url_fragment")

    def test_refresh_subscription_clears_auto_managed_routing_profile_when_metadata_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            real_home = project_root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            (project_root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, project_root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")

            routing_uri = happ_routing_uri(
                {"name": "Ephemeral route", "directsites": ["geosite:cn"], "directip": ["geoip:cn"]},
                mode="onadd",
            )
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(single_vless_line(), {"ETag": "etag-1", "routing": routing_uri, "providerid": "provider-temp"}),
                    FakeResponse(b"geoip-bytes"),
                    FakeResponse(b"geosite-bytes"),
                    FakeResponse(single_vless_line("Updated"), {"ETag": "etag-2"}),
                ],
            ):
                first_result = refresh_subscription(store, subscription["id"], paths=paths)
                second_result = refresh_subscription(store, subscription["id"], paths=paths)

            self.assertEqual(first_result["routing"]["status"], "created")
            self.assertEqual(second_result["routing"]["status"], "none")
            self.assertEqual(store["subscriptions"][0]["provider_id"], "")
            self.assertEqual(store["subscriptions"][0]["provider_id_source"], "")
            self.assertIsNone(store["subscriptions"][0]["routing_profile_id"])
            self.assertEqual(store["subscriptions"][0]["last_routing_status"], "none")
            self.assertEqual(store["subscriptions"][0]["last_routing_error"], "")
            self.assertEqual(store["routing"]["profiles"], [])
            self.assertIsNone(store["routing"]["active_profile_id"])
            self.assertFalse(store["routing"]["enabled"])


if __name__ == "__main__":
    unittest.main()
