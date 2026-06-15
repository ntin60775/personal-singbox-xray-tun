"""Unit-тесты инфраструктурного слоя: репозитории и Unit of Work."""
from __future__ import annotations

import unittest

from gui.domain import (
    Node,
    Profile,
    ProtocolConfig,
    RoutingProfile,
    Subscription,
    node_from_store_dict,
    node_to_store_dict,
)
from gui.infrastructure import (
    JsonNodeRepository,
    JsonProfileRepository,
    JsonSubscriptionRepository,
    JsonRoutingRepository,
    StoreUnitOfWork,
)


def _make_store_with_manual_profile() -> dict:
    return {
        "version": 3,
        "profiles": [
            {
                "id": "manual",
                "kind": "manual",
                "name": "Ручной профиль",
                "enabled": True,
                "source_subscription_id": None,
                "nodes": [
                    {
                        "id": "node-1",
                        "fingerprint": "abc",
                        "name": "Test Node",
                        "protocol": "vless",
                        "raw_uri": "vless://...",
                        "enabled": True,
                        "user_renamed": False,
                        "parse_error": "",
                        "normalized": {
                            "protocol": "vless",
                            "address": "1.2.3.4",
                            "port": 443,
                        },
                        "created_at": "",
                        "updated_at": "",
                        "origin": {"kind": "manual_import", "subscription_id": None},
                    }
                ],
            }
        ],
        "subscriptions": [
            {
                "id": "sub-1",
                "url": "https://example.com/sub",
                "name": "Test Sub",
                "enabled": True,
                "etag": "",
                "last_modified": "",
                "last_success_at": None,
                "last_status": "never",
                "last_error": "",
                "profile_id": "manual",
                "provider_id": "",
                "provider_id_source": "",
                "routing_profile_id": None,
                "last_routing_status": "never",
                "last_routing_error": "",
            }
        ],
        "active_selection": {
            "profile_id": "manual",
            "node_id": "node-1",
            "activated_at": None,
            "source": None,
        },
        "routing": {
            "enabled": False,
            "active_profile_id": None,
            "profiles": [],
            "runtime_ready": False,
            "runtime_error": "",
            "geodata": {},
        },
        "meta": {"initialized_at": "2026-01-01T00:00:00"},
    }


class TestJsonNodeRepository(unittest.TestCase):
    def setUp(self):
        self.store = _make_store_with_manual_profile()
        self.repo = JsonNodeRepository(self.store)

    def test_get_active(self):
        node = self.repo.get_active()
        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.id, "node-1")
        self.assertEqual(node.profile_id, "manual")

    def test_get_by_id(self):
        node = self.repo.get_by_id("manual", "node-1")
        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.id, "node-1")

    def test_get_by_id_not_found(self):
        node = self.repo.get_by_id("manual", "nonexistent")
        self.assertIsNone(node)

    def test_get_by_id_wrong_profile(self):
        node = self.repo.get_by_id("nonexistent", "node-1")
        self.assertIsNone(node)

    def test_save_new_node(self):
        node = Node(
            id="node-2",
            profile_id="manual",
            name="New Node",
            protocol_config=ProtocolConfig(protocol="vless", address="5.6.7.8", port=443),
        )
        self.repo.save("manual", node)
        found = self.repo.get_by_id("manual", "node-2")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.name, "New Node")

    def test_save_updates_existing(self):
        node = self.repo.get_by_id("manual", "node-1")
        assert node is not None
        node.name = "Updated Node"
        self.repo.save("manual", node)
        found = self.repo.get_by_id("manual", "node-1")
        assert found is not None
        self.assertEqual(found.name, "Updated Node")

    def test_delete(self):
        self.repo.delete("manual", "node-1")
        self.assertIsNone(self.repo.get_by_id("manual", "node-1"))

    def test_delete_nonexistent(self):
        self.repo.delete("manual", "nonexistent")  # не должно бросать


class TestJsonProfileRepository(unittest.TestCase):
    def setUp(self):
        self.store = _make_store_with_manual_profile()
        self.repo = JsonProfileRepository(self.store)

    def test_get_all(self):
        profiles = self.repo.get_all()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].id, "manual")

    def test_get_by_id(self):
        profile = self.repo.get_by_id("manual")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertTrue(profile.has_nodes())

    def test_save_new_profile(self):
        profile = Profile(id="new-prof", name="New Profile", kind="manual")
        self.repo.save(profile)
        found = self.repo.get_by_id("new-prof")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.name, "New Profile")


class TestJsonSubscriptionRepository(unittest.TestCase):
    def setUp(self):
        self.store = _make_store_with_manual_profile()
        self.repo = JsonSubscriptionRepository(self.store)

    def test_get_all(self):
        subs = self.repo.get_all()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].id, "sub-1")

    def test_get_by_id(self):
        sub = self.repo.get_by_id("sub-1")
        self.assertIsNotNone(sub)
        assert sub is not None
        self.assertEqual(sub.url, "https://example.com/sub")

    def test_save_new(self):
        sub = Subscription(id="sub-2", url="https://example.com/sub2", name="Sub 2")
        self.repo.save(sub)
        found = self.repo.get_by_id("sub-2")
        self.assertIsNotNone(found)

    def test_save_updates(self):
        sub = self.repo.get_by_id("sub-1")
        assert sub is not None
        sub.name = "Updated Sub"
        self.repo.save(sub)
        found = self.repo.get_by_id("sub-1")
        assert found is not None
        self.assertEqual(found.name, "Updated Sub")


class TestJsonRoutingRepository(unittest.TestCase):
    def setUp(self):
        self.store = _make_store_with_manual_profile()
        self.repo = JsonRoutingRepository(self.store)

    def test_get_all_empty(self):
        profiles = self.repo.get_all()
        self.assertEqual(len(profiles), 0)

    def test_get_active_none(self):
        rp = self.repo.get_active()
        self.assertIsNone(rp)

    def test_save_preserves_all_fields(self):
        """После save -> get_by_id все 12 новых полей сохраняются."""
        rp = RoutingProfile(
            id="test-roundtrip-1",
            name="Roundtrip Test",
            name_key="roundtrip_test",
            enabled=True,
            auto_managed=False,
            source_kind="manual_import",
            source_format="json",
            activation_mode="manual",
            global_proxy=True,
            domain_strategy="AsIs",
            geoip_url="https://geoip.example.com",
            geosite_url="https://geosite.example.com",
            direct_sites=["geosite:private"],
            direct_ip=["10.0.0.0/8"],
            proxy_sites=["geosite:google"],
            proxy_ip=[],
            block_sites=["geosite:ads"],
            block_ip=[],
            dns_hosts={"test.example": "1.2.3.4"},
            route_order=["block", "direct", "proxy"],
            source_subscription_id=None,
            provider_id="test",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-06-01T00:00:00",
            raw_payload={"name": "test", "key": "val"},
            domestic_dns_domain="lan",
            domestic_dns_ip="192.168.1.1",
            domestic_dns_type="udp",
            remote_dns_domain="cloudflare",
            remote_dns_ip="1.1.1.1",
            remote_dns_type="tcp",
            fake_dns=True,
            last_updated="2026-01-01",
            supported_entry_count=5,
            stored_only_fields=["dns_hosts", "fake_dns"],
            ignored_fields=["domainstrategy=InvalidValue"],
            unknown_fields=["extra_field"],
        )
        self.repo.save(rp)
        found = self.repo.get_by_id(rp.id)
        self.assertIsNotNone(found)

        # проверка 12 новых полей
        self.assertEqual(found.raw_payload, {"name": "test", "key": "val"})
        self.assertEqual(found.domestic_dns_domain, "lan")
        self.assertEqual(found.domestic_dns_ip, "192.168.1.1")
        self.assertEqual(found.domestic_dns_type, "udp")
        self.assertEqual(found.remote_dns_domain, "cloudflare")
        self.assertEqual(found.remote_dns_ip, "1.1.1.1")
        self.assertEqual(found.remote_dns_type, "tcp")
        self.assertTrue(found.fake_dns)
        self.assertEqual(found.last_updated, "2026-01-01")
        self.assertEqual(found.supported_entry_count, 5)
        self.assertEqual(found.stored_only_fields, ["dns_hosts", "fake_dns"])
        self.assertEqual(found.ignored_fields, ["domainstrategy=InvalidValue"])
        self.assertEqual(found.unknown_fields, ["extra_field"])

        # дополнительная проверка старых полей
        self.assertEqual(found.id, "test-roundtrip-1")
        self.assertEqual(found.name, "Roundtrip Test")
        self.assertTrue(found.global_proxy)
        self.assertEqual(found.direct_sites, ["geosite:private"])
        self.assertEqual(found.route_order, ["block", "direct", "proxy"])
        self.assertEqual(found.provider_id, "test")

    def test_activate_and_deactivate(self):
        """Активация/деактивация через репозиторий."""
        rp = RoutingProfile(
            id="test-profile-1",
            name="Test Profile",
        )
        self.repo.save(rp)

        self.assertIsNone(self.repo.get_active())

        self.repo.activate("test-profile-1")
        active = self.repo.get_active()
        self.assertIsNotNone(active)
        self.assertEqual(active.id, "test-profile-1")

        self.repo.deactivate()
        self.assertIsNone(self.repo.get_active())


if __name__ == "__main__":
    unittest.main()
