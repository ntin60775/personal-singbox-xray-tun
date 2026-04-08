from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_runtime import (  # noqa: E402
    apply_transport_hints_to_runtime_config,
    render_runtime_config,
)


TEMPLATE_CONFIG = {
    "log": {"loglevel": "info"},
    "inbounds": [{"tag": "socks-in", "listen": "127.0.0.1", "port": 10808}],
    "outbounds": [
        {
            "tag": "proxy",
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": "template.example.com",
                        "port": 443,
                        "users": [{"id": "REPLACE_WITH_REALITY_UUID", "encryption": "none"}],
                    }
                ]
            },
            "streamSettings": {
                "network": "xhttp",
                "security": "reality",
                "sockopt": {"interface": "eth0"},
                "realitySettings": {
                    "serverName": "template.example.com",
                    "fingerprint": "chrome",
                    "publicKey": "REPLACE_WITH_REALITY_PUBLIC_KEY",
                    "shortId": "REPLACE_WITH_REALITY_SHORT_ID",
                    "spiderX": "/",
                },
                "xhttpSettings": {"host": "template.example.com", "path": "/", "mode": "auto", "extra": {"headers": {}}},
            },
        },
        {"tag": "direct", "protocol": "freedom"},
        {"tag": "block", "protocol": "blackhole"},
    ],
    "routing": {"rules": [{"outboundTag": "proxy"}]},
}


class SubvostRuntimeTests(unittest.TestCase):
    def test_repo_template_keeps_ip_literal_default_doh_fallback(self) -> None:
        template = json.loads((REPO_ROOT / "xray-tun-subvost.json").read_text(encoding="utf-8"))
        self.assertEqual(template["dns"]["servers"][1], "https://8.8.8.8/dns-query")

    def test_render_runtime_replaces_only_proxy_outbound(self) -> None:
        normalized_node = {
            "enabled": True,
            "parse_error": "",
            "normalized": {
                "protocol": "trojan",
                "address": "edge.example.com",
                "port": 443,
                "password": "secret",
                "network": "grpc",
                "security": "tls",
                "host": "",
                "path": "",
                "server_name": "edge.example.com",
                "service_name": "grpc-service",
                "grpc_authority": "",
                "fingerprint": "",
                "public_key": "",
                "short_id": "",
                "spider_x": "/",
                "mode": "auto",
                "xhttp_extra": {},
                "alpn": [],
                "allow_insecure": False,
            },
        }

        rendered = render_runtime_config(copy.deepcopy(TEMPLATE_CONFIG), normalized_node)
        self.assertEqual(rendered["outbounds"][0]["protocol"], "trojan")
        self.assertEqual(rendered["outbounds"][0]["settings"]["servers"][0]["address"], "edge.example.com")
        self.assertEqual(rendered["outbounds"][0]["streamSettings"]["grpcSettings"]["serviceName"], "grpc-service")
        self.assertEqual(rendered["outbounds"][1], TEMPLATE_CONFIG["outbounds"][1])
        self.assertEqual(rendered["routing"], TEMPLATE_CONFIG["routing"])

    def test_render_runtime_preserves_xhttp_extra_from_node(self) -> None:
        normalized_node = {
            "enabled": True,
            "parse_error": "",
            "normalized": {
                "protocol": "vless",
                "address": "edge.example.com",
                "port": 443,
                "uuid": "11111111-1111-1111-1111-111111111111",
                "encryption": "none",
                "flow": "",
                "network": "xhttp",
                "security": "reality",
                "host": "edge.example.com",
                "path": "/",
                "server_name": "edge.example.com",
                "service_name": "",
                "grpc_authority": "",
                "fingerprint": "chrome",
                "public_key": "test-public-key",
                "short_id": "abcd1234",
                "spider_x": "/",
                "mode": "auto",
                "xhttp_extra": {"headers": {}, "xPaddingBytes": "100-1000"},
                "alpn": [],
                "allow_insecure": False,
            },
        }

        rendered = render_runtime_config(copy.deepcopy(TEMPLATE_CONFIG), normalized_node)
        self.assertEqual(
            rendered["outbounds"][0]["streamSettings"]["xhttpSettings"]["extra"],
            {"headers": {}, "xPaddingBytes": "100-1000"},
        )

    def test_render_runtime_applies_routing_profile_overlay(self) -> None:
        template = copy.deepcopy(TEMPLATE_CONFIG)
        template["routing"] = {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "inboundTag": ["tun-in"], "port": "53", "outboundTag": "dns-out"},
                {"type": "field", "inboundTag": ["tun-in"], "network": "tcp,udp", "outboundTag": "proxy"},
            ],
        }
        normalized_node = {
            "enabled": True,
            "parse_error": "",
            "normalized": {
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
                "xhttp_extra": {},
                "alpn": [],
                "allow_insecure": False,
            },
        }
        routing_profile = {
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

        rendered = render_runtime_config(template, normalized_node, routing_profile=routing_profile)
        routing_rules = rendered["routing"]["rules"]

        self.assertEqual(rendered["routing"]["domainStrategy"], "IPIfNonMatch")
        self.assertEqual(routing_rules[0]["outboundTag"], "dns-out")
        self.assertEqual(routing_rules[1]["outboundTag"], "block")
        self.assertEqual(routing_rules[2]["outboundTag"], "direct")
        self.assertEqual(routing_rules[3]["outboundTag"], "proxy")
        self.assertEqual(routing_rules[-1]["outboundTag"], "direct")

    def test_apply_transport_hints_updates_proxy_and_direct_outbounds(self) -> None:
        active_config = copy.deepcopy(TEMPLATE_CONFIG)
        rendered = apply_transport_hints_to_runtime_config(
            active_config,
            default_interface="wlp3s0",
            outbound_mark=8421,
        )

        self.assertEqual(rendered["outbounds"][0]["settings"], active_config["outbounds"][0]["settings"])
        self.assertEqual(rendered["outbounds"][0]["streamSettings"]["sockopt"]["interface"], "wlp3s0")
        self.assertEqual(rendered["outbounds"][0]["streamSettings"]["sockopt"]["mark"], 8421)
        self.assertEqual(rendered["outbounds"][1]["streamSettings"]["sockopt"]["interface"], "wlp3s0")
        self.assertEqual(rendered["outbounds"][1]["streamSettings"]["sockopt"]["mark"], 8421)
        self.assertEqual(rendered["outbounds"][2], active_config["outbounds"][2])
        self.assertEqual(rendered["routing"]["rules"], active_config["routing"]["rules"])


if __name__ == "__main__":
    unittest.main()
