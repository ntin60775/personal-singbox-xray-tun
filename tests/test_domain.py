"""Unit-тесты доменного слоя."""
from __future__ import annotations

import unittest

from gui.domain import (
    Node,
    NodeAddress,
    Profile,
    ProtocolConfig,
    RoutingProfile,
    Subscription,
    TransportHint,
    node_from_store_dict,
    node_to_store_dict,
    profile_from_store_dict,
    profile_to_store_dict,
    subscription_from_store_dict,
    routing_profile_from_store_dict,
)


class TestNodeAddress(unittest.TestCase):
    def test_creation(self):
        addr = NodeAddress(host="1.2.3.4", port=443, transport="ws")
        self.assertEqual(addr.host, "1.2.3.4")
        self.assertEqual(addr.port, 443)
        self.assertEqual(addr.transport, "ws")

    def test_str(self):
        addr = NodeAddress(host="1.2.3.4", port=443, transport="tcp")
        self.assertEqual(str(addr), "1.2.3.4:443/tcp")

    def test_immutable(self):
        addr = NodeAddress(host="1.2.3.4", port=443)
        with self.assertRaises(Exception):
            addr.host = "changed"  # type: ignore


class TestProtocolConfig(unittest.TestCase):
    def test_is_tls(self):
        pc = ProtocolConfig(protocol="vless", address="1.2.3.4", port=443, security="tls")
        self.assertTrue(pc.is_tls)
        self.assertFalse(pc.is_reality)

    def test_is_reality(self):
        pc = ProtocolConfig(protocol="vless", address="1.2.3.4", port=443, security="reality")
        self.assertTrue(pc.is_tls)
        self.assertTrue(pc.is_reality)

    def test_defaults(self):
        pc = ProtocolConfig(protocol="vless", address="1.2.3.4", port=443)
        self.assertEqual(pc.network, "tcp")
        self.assertEqual(pc.security, "none")
        self.assertEqual(pc.spider_x, "/")
        self.assertEqual(pc.encryption, "none")


class TestTransportHint(unittest.TestCase):
    def test_creation(self):
        hint = TransportHint(interface="tun0", mark=8421)
        self.assertEqual(hint.interface, "tun0")
        self.assertEqual(hint.mark, 8421)

    def test_none_defaults(self):
        hint = TransportHint()
        self.assertIsNone(hint.interface)
        self.assertIsNone(hint.mark)


class TestNode(unittest.TestCase):
    def test_is_valid_normal(self):
        node = Node(
            id="n1", profile_id="p1", name="Test",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443, uuid="real-uuid"),
        )
        self.assertTrue(node.is_valid())

    def test_is_valid_stub_address(self):
        node = Node(
            id="n1", profile_id="p1", name="Stub",
            protocol_config=ProtocolConfig(protocol="vless", address="0.0.0.0", port=1, uuid="real-uuid"),
        )
        self.assertFalse(node.is_valid())

    def test_is_valid_stub_uuid(self):
        node = Node(
            id="n1", profile_id="p1", name="Stub",
            protocol_config=ProtocolConfig(
                protocol="vless", address="1.2.3.4", port=443,
                uuid="00000000-0000-0000-0000-000000000000",
            ),
        )
        self.assertFalse(node.is_valid())

    def test_is_valid_parse_error(self):
        node = Node(
            id="n1", profile_id="p1", name="Stub",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443),
            parse_error="bad url",
        )
        self.assertFalse(node.is_valid())

    def test_matches_fingerprint(self):
        node = Node(
            id="n1", profile_id="p1", name="Test",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443),
            fingerprint="abc123",
        )
        self.assertTrue(node.matches_fingerprint("abc123"))
        self.assertFalse(node.matches_fingerprint("xyz789"))

    def test_address_property(self):
        node = Node(
            id="n1", profile_id="p1", name="Test",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443, network="ws"),
        )
        addr = node.address
        self.assertEqual(addr.host, "1.2.3.4")
        self.assertEqual(addr.port, 443)
        self.assertEqual(addr.transport, "ws")


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.node = Node(
            id="n1", profile_id="p1", name="Node 1",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443),
        )
        self.profile = Profile(id="p1", name="Test Profile", nodes=[self.node])

    def test_activate_node(self):
        activated = self.profile.activate_node("n1")
        self.assertEqual(activated.id, "n1")

    def test_activate_node_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            self.profile.activate_node("nonexistent")
        self.assertIn("не найден", str(ctx.exception))

    def test_activate_node_disabled(self):
        self.node.enabled = False
        with self.assertRaises(ValueError) as ctx:
            self.profile.activate_node("n1")
        self.assertIn("отключен", str(ctx.exception))

    def test_add_node_wrong_profile(self):
        node = Node(
            id="n2", profile_id="p2", name="Node 2",
            protocol_config=ProtocolConfig(protocol="vless", address="2.3.4.5", port=443),
        )
        with self.assertRaises(ValueError) as ctx:
            self.profile.add_node(node)
        self.assertIn("принадлежит профилю", str(ctx.exception))

    def test_add_node_correct(self):
        node = Node(
            id="n2", profile_id="p1", name="Node 2",
            protocol_config=ProtocolConfig(protocol="vless", address="2.3.4.5", port=443),
        )
        self.profile.add_node(node)
        self.assertEqual(len(self.profile.nodes), 2)

    def test_add_node_replaces_existing(self):
        node = Node(
            id="n1", profile_id="p1", name="Node 1 Updated",
            protocol_config=ProtocolConfig(protocol="vless", address="1.2.3.4", port=443),
        )
        self.profile.add_node(node)
        self.assertEqual(len(self.profile.nodes), 1)
        self.assertEqual(self.profile.nodes[0].name, "Node 1 Updated")

    def test_remove_node(self):
        self.profile.remove_node("n1")
        self.assertFalse(self.profile.has_nodes())

    def test_remove_node_nonexistent(self):
        self.profile.remove_node("n99")
        self.assertTrue(self.profile.has_nodes())

    def test_active_node_count(self):
        self.assertEqual(self.profile.active_node_count(), 1)
        self.node.enabled = False
        self.assertEqual(self.profile.active_node_count(), 0)


class TestSubscription(unittest.TestCase):
    def test_is_stale_never(self):
        sub = Subscription(id="s1", url="https://example.com", last_status="never")
        self.assertTrue(sub.is_stale())

    def test_is_stale_no_success(self):
        sub = Subscription(id="s1", url="https://example.com", last_status="ok", last_success_at=None)
        self.assertTrue(sub.is_stale())

    def test_has_nodes_no_profile(self):
        sub = Subscription(id="s1", url="https://example.com")
        self.assertFalse(sub.has_nodes())

    def test_has_nodes_with_profile(self):
        sub = Subscription(id="s1", url="https://example.com", profile_id="p1")
        self.assertTrue(sub.has_nodes())


class TestRoutingProfile(unittest.TestCase):
    def test_total_rules(self):
        rp = RoutingProfile(
            id="r1", name="Test",
            direct_sites=["example.com", "test.com"],
            proxy_sites=["google.com"],
            block_sites=["bad.com"],
            direct_ip=["10.0.0.0/8"],
        )
        self.assertEqual(rp.total_rules, 5)

    def test_has_geodata_urls(self):
        rp = RoutingProfile(id="r1", name="Test", geoip_url="https://...")
        self.assertTrue(rp.has_geodata_urls)
        rp2 = RoutingProfile(id="r2", name="Test")
        self.assertFalse(rp2.has_geodata_urls)


class TestNodeFactory(unittest.TestCase):
    def test_roundtrip_vless(self):
        d = {
            "id": "node-abc", "fingerprint": "sha256hex",
            "name": "VLESS Node", "protocol": "vless",
            "raw_uri": "vless://uuid@1.2.3.4:443?...",
            "enabled": True, "user_renamed": False, "parse_error": "",
            "normalized": {
                "protocol": "vless", "address": "1.2.3.4", "port": 443,
                "uuid": "test-uuid", "encryption": "none", "flow": "xtls-rprx-vision",
                "network": "tcp", "security": "reality",
                "server_name": "example.com", "public_key": "key123", "short_id": "abc",
                "fingerprint": "chrome",
            },
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "origin": {"kind": "manual_import", "subscription_id": None},
        }
        node = node_from_store_dict(d)
        self.assertEqual(node.id, "node-abc")
        self.assertEqual(node.protocol, "vless")
        self.assertTrue(node.is_valid())

        d2 = node_to_store_dict(node)
        node2 = node_from_store_dict(d2)
        self.assertEqual(node2.id, node.id)
        self.assertEqual(node2.protocol_config.uuid, "test-uuid")
        self.assertEqual(node2.protocol_config.security, "reality")

    def test_roundtrip_vmess(self):
        d = {
            "id": "node-vm", "fingerprint": "sha256",
            "name": "VMess Node", "protocol": "vmess",
            "raw_uri": "vmess://...",
            "enabled": True, "user_renamed": False, "parse_error": "",
            "normalized": {
                "protocol": "vmess", "address": "5.6.7.8", "port": 8080,
                "uuid": "vmess-uuid", "alter_id": 0, "cipher": "auto",
                "network": "ws", "security": "tls",
                "host": "ws.example.com", "path": "/ws",
            },
            "created_at": "", "updated_at": "",
            "origin": {"kind": "subscription", "subscription_id": "sub-1"},
        }
        node = node_from_store_dict(d)
        self.assertEqual(node.protocol_config.protocol, "vmess")
        self.assertEqual(node.protocol_config.alter_id, 0)
        self.assertEqual(node.protocol_config.network, "ws")

        d2 = node_to_store_dict(node)
        node2 = node_from_store_dict(d2)
        self.assertEqual(node2.protocol_config.uuid, "vmess-uuid")

    def test_roundtrip_with_transport_hint(self):
        d = {
            "id": "node-th", "fingerprint": "sha",
            "name": "Hinted Node", "protocol": "vless",
            "raw_uri": "vless://...",
            "enabled": True, "user_renamed": False, "parse_error": "",
            "normalized": {
                "protocol": "vless", "address": "1.2.3.4", "port": 443,
                "network": "tcp", "security": "none",
                "interface": "eth0", "mark": 255,
            },
            "created_at": "", "updated_at": "",
            "origin": {"kind": "manual", "subscription_id": None},
        }
        node = node_from_store_dict(d)
        self.assertIsNotNone(node.transport_hint)
        assert node.transport_hint is not None  # type narrowing
        self.assertEqual(node.transport_hint.interface, "eth0")
        self.assertEqual(node.transport_hint.mark, 255)


class TestProfileFactory(unittest.TestCase):
    def test_roundtrip(self):
        d = {
            "id": "prof-1", "name": "Test Profile", "kind": "manual",
            "enabled": True, "source_subscription_id": None,
            "nodes": [
                {
                    "id": "n1", "fingerprint": "sha", "name": "N1",
                    "protocol": "vless", "raw_uri": "vless://...",
                    "enabled": True, "user_renamed": False, "parse_error": "",
                    "normalized": {"protocol": "vless", "address": "1.2.3.4", "port": 443},
                    "created_at": "", "updated_at": "",
                    "origin": {"kind": "manual", "subscription_id": None},
                }
            ],
        }
        profile = profile_from_store_dict(d)
        self.assertEqual(profile.id, "prof-1")
        self.assertEqual(profile.active_node_count(), 1)
        self.assertEqual(profile.nodes[0].profile_id, "prof-1")

        d2 = profile_to_store_dict(profile)
        profile2 = profile_from_store_dict(d2)
        self.assertEqual(profile2.id, "prof-1")
        self.assertEqual(profile2.nodes[0].profile_id, "prof-1")


class TestSubscriptionFactory(unittest.TestCase):
    def test_roundtrip(self):
        d = {
            "id": "sub-1", "url": "https://example.com/sub",
            "name": "Test Sub", "enabled": True,
            "etag": "abc", "last_modified": "Mon, 01 Jan 2026",
            "last_success_at": "2026-01-01T00:00:00",
            "last_status": "ok", "last_error": "",
            "profile_id": "prof-1",
            "provider_id": "prov-1", "provider_id_source": "header",
            "routing_profile_id": None,
            "last_routing_status": "never", "last_routing_error": "",
        }
        sub = subscription_from_store_dict(d)
        self.assertEqual(sub.id, "sub-1")
        self.assertEqual(sub.last_status, "ok")
        self.assertTrue(sub.has_nodes())
        self.assertFalse(sub.is_stale(max_age_days=999))


class TestRoutingProfileFactory(unittest.TestCase):
    def test_from_store_dict(self):
        d = {
            "id": "rp-1", "name": "Test Routing",
            "name_key": "test routing",
            "enabled": True, "auto_managed": False,
            "source_kind": "manual_import", "source_format": "json",
            "activation_mode": "manual",
            "global_proxy": False, "domain_strategy": "AsIs",
            "geoip_url": "https://geoip.example.com",
            "geosite_url": "",
            "direct_sites": ["example.com"], "direct_ip": [],
            "proxy_sites": [], "proxy_ip": [],
            "block_sites": [], "block_ip": [],
            "dns_hosts": {}, "route_order": ["block", "direct", "proxy"],
            "source_subscription_id": None, "provider_id": "",
            "created_at": "", "updated_at": "",
        }
        rp = routing_profile_from_store_dict(d)
        self.assertEqual(rp.id, "rp-1")
        self.assertTrue(rp.has_geodata_urls)
        self.assertEqual(rp.total_rules, 1)


if __name__ == "__main__":
    unittest.main()
