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
    build_direct_routes_report,
    download_routing_geodata,
    extract_direct_rules_from_xray_config,
    extract_direct_rules_from_routing_profile,
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
        self.assertEqual(profile["activation_mode"], "add")
        self.assertEqual(profile["domain_strategy"], "IPIfNonMatch")
        self.assertTrue(profile["global_proxy"])
        self.assertEqual(profile["direct_sites"], ["geosite:private"])
        self.assertEqual(profile["direct_ip"], ["geoip:private"])
        self.assertEqual(profile["supported_entry_count"], 4)

    def test_parse_routing_profile_from_happ_onadd_tracks_activation_mode(self) -> None:
        payload = {
            "name": "OnAdd",
            "directsites": ["geosite:cn"],
            "directip": ["geoip:cn"],
            "proxysites": ["geosite:geolocation-!cn"],
            "proxyip": ["geoip:amazon"],
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        profile = parse_routing_profile_input(f"happ://routing/onadd/{encoded}")

        self.assertEqual(profile["activation_mode"], "onadd")
        self.assertEqual(profile["direct_sites"], ["geosite:cn"])
        self.assertEqual(profile["direct_ip"], ["geoip:cn"])
        self.assertEqual(profile["proxy_sites"], ["geosite:geolocation-!cn"])
        self.assertEqual(profile["proxy_ip"], ["geoip:amazon"])

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

    def test_extract_direct_rules_from_xray_config_skips_direct_catchall(self) -> None:
        config = {
            "routing": {
                "rules": [
                    {
                        "type": "field",
                        "domain": ["geosite:private"],
                        "ip": ["10.0.0.0/8"],
                        "outboundTag": "direct",
                    },
                    {
                        "type": "field",
                        "inboundTag": ["tun-in"],
                        "network": "tcp,udp",
                        "outboundTag": "direct",
                    },
                ]
            }
        }

        entries = extract_direct_rules_from_xray_config(
            config,
            source="template",
            source_label="Шаблон",
            priority=10,
            reason="Зашито.",
        )

        self.assertEqual([(entry["kind"], entry["value"]) for entry in entries], [("domain", "geosite:private"), ("ip", "10.0.0.0/8")])
        self.assertTrue(all(entry["source"] == "template" for entry in entries))

    def test_extract_direct_rules_from_routing_profile_reads_direct_fields_only(self) -> None:
        profile = {
            "name": "SubVostVPN",
            "direct_sites": ["geosite:private"],
            "direct_ip": ["geoip:private"],
            "proxy_sites": ["geosite:youtube"],
            "block_ip": ["203.0.113.0/24"],
        }

        entries = extract_direct_rules_from_routing_profile(profile)

        self.assertEqual([(entry["kind"], entry["value"]) for entry in entries], [("domain", "geosite:private"), ("ip", "geoip:private")])
        self.assertTrue(all(entry["source"] == "profile" for entry in entries))

    def test_build_direct_routes_report_marks_template_priority_conflicts(self) -> None:
        template = {
            "routing": {
                "rules": [
                    {"type": "field", "ip": ["10.0.0.0/8"], "outboundTag": "direct"},
                    {"type": "field", "domain": ["domain:localhost"], "outboundTag": "direct"},
                    {"type": "field", "inboundTag": ["tun-in"], "network": "tcp,udp", "outboundTag": "proxy"},
                ]
            }
        }
        profile = {
            "name": "Office",
            "direct_sites": ["domain:localhost"],
            "direct_ip": ["geoip:private"],
            "proxy_sites": [],
            "proxy_ip": ["10.2.12.56"],
            "block_sites": [],
            "block_ip": [],
        }
        runtime = apply_routing_profile_to_config(template, {**profile, "global_proxy": False, "route_order": ["direct", "proxy", "block"]})

        report = build_direct_routes_report(
            template_config=template,
            active_profile=profile,
            runtime_config=runtime,
        )

        self.assertEqual(report["summary"]["template_count"], 2)
        self.assertEqual(report["summary"]["profile_count"], 2)
        self.assertGreaterEqual(report["summary"]["runtime_count"], 4)
        self.assertEqual(report["summary"]["conflict_count"], 1)
        conflict = report["conflicts"][0]
        self.assertEqual(conflict["policy"], "proxy")
        self.assertEqual(conflict["value"], "10.2.12.56")
        covered = [entry for entry in report["entries"] if entry["source"] == "profile" and entry["value"] == "domain:localhost"]
        self.assertEqual(covered[0]["covered_by"][0]["source"], "template")

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
