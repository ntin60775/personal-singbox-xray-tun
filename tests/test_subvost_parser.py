from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_parser import (  # noqa: E402
    ParseError,
    extract_subscription_metadata,
    parse_proxy_uri,
    parse_subscription_payload,
)


class SubvostParserTests(unittest.TestCase):
    def test_parse_vless_reality_xhttp(self) -> None:
        raw_uri = (
            "vless://11111111-1111-1111-1111-111111111111@example.com:443"
            "?type=xhttp&security=reality&sni=edge.example.com&pbk=test-public-key"
            "&sid=abcd1234&fp=chrome&host=edge.example.com&path=%2Fentry"
            "&extra=%7B%22headers%22%3A%7B%7D%7D#Example"
        )
        normalized = parse_proxy_uri(raw_uri)
        self.assertEqual(normalized["protocol"], "vless")
        self.assertEqual(normalized["network"], "xhttp")
        self.assertEqual(normalized["security"], "reality")
        self.assertEqual(normalized["server_name"], "edge.example.com")
        self.assertEqual(normalized["xhttp_extra"], {"headers": {}})
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

    def test_parse_subscription_payload_ignores_happ_routing_line(self) -> None:
        payload = (
            "happ://routing/add/eyJuYW1lIjoiVGVzdCJ9\n"
            "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
        ).encode("utf-8")
        lines, payload_format = parse_subscription_payload(payload)
        self.assertEqual(payload_format, "plain_text")
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("vless://"))

    def test_parse_subscription_payload_base64_ignores_happ_routing_and_provider_id_comment(self) -> None:
        routing_uri = "happ://routing/add/eyJOYW1lIjoiUm91dGluZyJ9"
        raw = (
            "#profile-title Example\n"
            "#providerid body-provider\n"
            f"{routing_uri}\n"
            "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
        )
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8"))

        lines, payload_format = parse_subscription_payload(encoded)

        self.assertEqual(payload_format, "base64")
        self.assertEqual(
            lines,
            ["vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node"],
        )

    def test_extract_subscription_metadata_prefers_response_headers(self) -> None:
        payload = (
            "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
        ).encode("utf-8")
        metadata = extract_subscription_metadata(
            payload,
            headers={
                "routing": "happ://routing/onadd/eyJOYW1lIjoiSGVhZGVyIn0",
                "providerid": "provider-header",
            },
            source_url="https://example.com/sub#?providerid=url-fragment",
        )

        self.assertEqual(metadata["routing_text"], "happ://routing/onadd/eyJOYW1lIjoiSGVhZGVyIn0")
        self.assertEqual(metadata["routing_source"], "response_header")
        self.assertEqual(metadata["provider_id"], "provider-header")
        self.assertEqual(metadata["provider_id_source"], "response_header")

    def test_extract_subscription_metadata_reads_routing_and_provider_id_from_body(self) -> None:
        routing_uri = "happ://routing/onadd/eyJOYW1lIjoiQm9keSJ9"
        payload = (
            "#profile-title Example\n"
            "#providerid provider-body\n"
            f"{routing_uri}\n"
            "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
        ).encode("utf-8")

        metadata = extract_subscription_metadata(payload)

        self.assertEqual(metadata["payload_format"], "plain_text")
        self.assertEqual(metadata["routing_text"], routing_uri)
        self.assertEqual(metadata["routing_source"], "body_plain_text")
        self.assertEqual(metadata["provider_id"], "provider-body")
        self.assertEqual(metadata["provider_id_source"], "body_plain_text")

    def test_extract_subscription_metadata_reads_provider_id_from_url_fragment(self) -> None:
        payload = (
            "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
        ).encode("utf-8")

        metadata = extract_subscription_metadata(payload, source_url="https://example.com/sub#?providerid=url-fragment")

        self.assertEqual(metadata["provider_id"], "url-fragment")
        self.assertEqual(metadata["provider_id_source"], "url_fragment")
        self.assertEqual(metadata["routing_text"], "")

    def test_provider_placeholder_link_is_rejected(self) -> None:
        raw_uri = (
            "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1"
            "?type=tcp&security=none#Приложение не поддерживаетя"
        )
        with self.assertRaisesRegex(ParseError, "заглушку"):
            parse_proxy_uri(raw_uri)

    def test_provider_device_limit_placeholder_surfaces_exact_reason(self) -> None:
        raw_uri = (
            "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1"
            "?type=tcp&security=none#Достигнут%20лимит%20устройств"
        )
        with self.assertRaisesRegex(ParseError, "Достигнут лимит устройств"):
            parse_proxy_uri(raw_uri)


if __name__ == "__main__":
    unittest.main()
