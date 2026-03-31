from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_runtime import extract_node_from_existing_config, render_runtime_config  # noqa: E402


TEMPLATE_CONFIG = {
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
    ],
    "routing": {"rules": [{"outboundTag": "proxy"}]},
}


class SubvostRuntimeTests(unittest.TestCase):
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

    def test_extract_node_from_existing_config(self) -> None:
        config = copy.deepcopy(TEMPLATE_CONFIG)
        config["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"] = "live-uuid"
        config["outbounds"][0]["streamSettings"]["realitySettings"]["publicKey"] = "live-public"
        config["outbounds"][0]["streamSettings"]["realitySettings"]["shortId"] = "live-short"
        normalized = extract_node_from_existing_config(config)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["protocol"], "vless")
        self.assertEqual(normalized["security"], "reality")
        self.assertEqual(normalized["public_key"], "live-public")


if __name__ == "__main__":
    unittest.main()
