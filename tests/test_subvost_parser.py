from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_parser import ParseError, parse_proxy_uri, parse_subscription_payload  # noqa: E402


class SubvostParserTests(unittest.TestCase):
    def test_parse_vless_reality_xhttp(self) -> None:
        raw_uri = (
            "vless://11111111-1111-1111-1111-111111111111@example.com:443"
            "?type=xhttp&security=reality&sni=edge.example.com&pbk=test-public-key"
            "&sid=abcd1234&fp=chrome&host=edge.example.com&path=%2Fentry#Example"
        )
        normalized = parse_proxy_uri(raw_uri)
        self.assertEqual(normalized["protocol"], "vless")
        self.assertEqual(normalized["network"], "xhttp")
        self.assertEqual(normalized["security"], "reality")
        self.assertEqual(normalized["server_name"], "edge.example.com")
        self.assertEqual(normalized["display_name"], "Example")
        self.assertTrue(normalized["fingerprint_hash"])

    def test_parse_vmess_ws(self) -> None:
        payload = {
            "v": "2",
            "ps": "VMess node",
            "add": "vmess.example.com",
            "port": "443",
            "id": "22222222-2222-2222-2222-222222222222",
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": "cdn.example.com",
            "path": "/socket",
            "tls": "tls",
            "sni": "cdn.example.com",
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        normalized = parse_proxy_uri(f"vmess://{encoded}")
        self.assertEqual(normalized["protocol"], "vmess")
        self.assertEqual(normalized["network"], "ws")
        self.assertEqual(normalized["host"], "cdn.example.com")
        self.assertEqual(normalized["path"], "/socket")

    def test_parse_trojan_grpc(self) -> None:
        raw_uri = (
            "trojan://secret@example.com:443"
            "?type=grpc&security=tls&sni=edge.example.com&serviceName=grpc-service#Trojan"
        )
        normalized = parse_proxy_uri(raw_uri)
        self.assertEqual(normalized["protocol"], "trojan")
        self.assertEqual(normalized["service_name"], "grpc-service")
        self.assertEqual(normalized["security"], "tls")

    def test_shadowsocks_plugin_is_rejected(self) -> None:
        with self.assertRaises(ParseError):
            parse_proxy_uri("ss://YWVzLTI1Ni1nY206cGFzcw==@example.com:8388?plugin=v2ray-plugin")

    def test_parse_shadowsocks_direct_uri_decodes_percent_encoded_password(self) -> None:
        normalized = parse_proxy_uri("ss://aes-256-gcm:pa%2Fss@example.com:8388#DirectSS")
        self.assertEqual(normalized["protocol"], "ss")
        self.assertEqual(normalized["password"], "pa/ss")

    def test_parse_subscription_payload_plain_text(self) -> None:
        lines, payload_format = parse_subscription_payload(
            b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none\n"
        )
        self.assertEqual(payload_format, "plain_text")
        self.assertEqual(len(lines), 1)

    def test_parse_subscription_payload_base64(self) -> None:
        raw = "ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#SS"
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8"))
        lines, payload_format = parse_subscription_payload(encoded)
        self.assertEqual(payload_format, "base64")
        self.assertEqual(lines, [raw])


if __name__ == "__main__":
    unittest.main()
