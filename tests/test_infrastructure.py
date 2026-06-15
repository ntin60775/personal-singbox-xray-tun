"""Unit-тесты инфраструктурного слоя: репозитории и Unit of Work."""
from __future__ import annotations

import unittest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from gui.infrastructure.adapters import ShellRuntimeAdapter, CommandResult


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


class TestShellRuntimeAdapter(unittest.TestCase):
    """Тесты ShellRuntimeAdapter."""

    def test_run_script_timeout_returns_command_result(self) -> None:
        """run_script возвращает CommandResult с ошибкой при таймауте subprocess."""
        adapter = ShellRuntimeAdapter(
            project_root=Path("/tmp"),
            libexec_dir=Path("/tmp"),
        )
        with patch("gui.infrastructure.adapters.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=180)):
            result = adapter.run_script("Тест", Path("script.sh"))

        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, -1)
        self.assertIn("превысило таймаут", result.output)

if __name__ == "__main__":
    unittest.main()
