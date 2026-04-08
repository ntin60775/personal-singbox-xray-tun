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
from subvost_routing import (  # noqa: E402
    apply_routing_profile_to_config,
    download_routing_geodata,
    parse_routing_profile_input,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class SubvostRoutingTests(unittest.TestCase):
    def test_parse_routing_profile_from_happ_uri(self) -> None:
        payload = {
            "name": "SubVostVPN",
            "globalproxy": True,
            "domainstrategy": "IPIfNonMatch",
            "directsites": ["geosite:private"],
            "directip": ["geoip:private"],
            "proxysites": ["geosite:youtube"],
            "proxyip": [],
            "blocksites": ["geosite:category-ads"],
            "blockip": [],
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        profile = parse_routing_profile_input(f"happ://routing/add/{encoded}")

        self.assertEqual(profile["name"], "SubVostVPN")
        self.assertEqual(profile["source_format"], "happ_uri")
        self.assertEqual(profile["domain_strategy"], "IPIfNonMatch")
        self.assertTrue(profile["global_proxy"])
        self.assertEqual(profile["supported_entry_count"], 4)

    def test_apply_routing_profile_to_config_preserves_internal_rules_and_updates_catchall(self) -> None:
        template = {
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {"type": "field", "inboundTag": ["tun-in"], "port": "53", "outboundTag": "dns-out"},
                    {"type": "field", "inboundTag": ["tun-in"], "network": "tcp,udp", "outboundTag": "proxy"},
                ],
            }
        }
        profile = {
            "global_proxy": False,
            "domain_strategy": "IPIfNonMatch",
            "route_order": ["block", "direct", "proxy"],
            "block_sites": ["geosite:category-ads"],
            "block_ip": [],
            "direct_sites": ["geosite:private"],
            "direct_ip": ["geoip:private"],
            "proxy_sites": ["geosite:youtube"],
            "proxy_ip": [],
        }

        rendered = apply_routing_profile_to_config(template, profile)
        rules = rendered["routing"]["rules"]

        self.assertEqual(rendered["routing"]["domainStrategy"], "IPIfNonMatch")
        self.assertEqual(rules[0]["outboundTag"], "dns-out")
        self.assertEqual(rules[1]["outboundTag"], "block")
        self.assertEqual(rules[2]["outboundTag"], "direct")
        self.assertEqual(rules[3]["outboundTag"], "proxy")
        self.assertEqual(rules[4]["outboundTag"], "direct")

    def test_download_routing_geodata_writes_both_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            real_home = Path(temp_dir) / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            profile = {
                "geoip_url": "https://example.com/geoip.dat",
                "geosite_url": "https://example.com/geosite.dat",
            }

            with patch(
                "subvost_routing.urllib.request.urlopen",
                side_effect=[FakeResponse(b"geoip-bytes"), FakeResponse(b"geosite-bytes")],
            ):
                status = download_routing_geodata(paths, profile)

            self.assertTrue(status["ready"])
            self.assertTrue(paths.geoip_asset_file.exists())
            self.assertTrue(paths.geosite_asset_file.exists())
            self.assertEqual(paths.geoip_asset_file.read_bytes(), b"geoip-bytes")
            self.assertEqual(paths.geosite_asset_file.read_bytes(), b"geosite-bytes")


if __name__ == "__main__":
    unittest.main()
