"""
E2E smoke test: verify the test infrastructure works correctly.
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import FakeService


class TestFakeService:
    """Verify FakeService stores and retrieves data correctly."""

    def test_service_initializes_store(self, fake_service: FakeService):
        """Store is initialized with manual profile and empty subscriptions."""
        store = fake_service.ensure_store_ready()
        assert store["version"] == 3
        assert len(store["profiles"]) >= 1  # manual profile
        manual = next(p for p in store["profiles"] if p["id"] == "manual")
        assert manual["kind"] == "manual"
        assert store["active_selection"]["profile_id"] is None
        assert store["active_selection"]["node_id"] is None

    def test_add_subscription_creates_profile(self, fake_service: FakeService):
        """Adding a subscription creates a linked profile."""
        result = fake_service.add_subscription("Test Sub", "https://example.com/sub")
        assert result["ok"] is True
        sub = result["subscription"]
        assert sub["name"] == "Test Sub"
        assert sub["profile_id"] is not None

        store = fake_service.ensure_store_ready()
        assert len(store["subscriptions"]) == 1

        profile = next(
            p for p in store["profiles"] if p["id"] == sub["profile_id"]
        )
        assert profile["kind"] == "subscription"

    def test_refresh_subscription_adds_nodes(self, fake_service: FakeService):
        """Refreshing a subscription parses fake nodes into the store."""
        result = fake_service.add_subscription("Test Sub", "https://example.com/sub")
        sub_id = result["subscription"]["id"]
        profile_id = result["subscription"]["profile_id"]

        refresh_result = fake_service.refresh_subscription(sub_id)
        assert refresh_result["ok"] is True

        store = fake_service.ensure_store_ready()
        profile = next(p for p in store["profiles"] if p["id"] == profile_id)
        assert len(profile["nodes"]) > 0
        for node in profile["nodes"]:
            assert node["protocol"] == "vless"
            assert node["id"].startswith("node-")

    def test_activate_node_sets_selection(self, fake_service: FakeService):
        """Activating a node updates active_selection."""
        result = fake_service.add_subscription("Test Sub", "https://example.com/sub")
        sub_id = result["subscription"]["id"]
        profile_id = result["subscription"]["profile_id"]
        fake_service.refresh_subscription(sub_id)

        store = fake_service.ensure_store_ready()
        profile = next(p for p in store["profiles"] if p["id"] == profile_id)
        node_id = profile["nodes"][0]["id"]

        activate_result = fake_service.activate_selection(profile_id, node_id)
        assert activate_result["ok"] is True

        store = fake_service.ensure_store_ready()
        assert store["active_selection"]["profile_id"] == profile_id
        assert store["active_selection"]["node_id"] == node_id

    def test_delete_subscription(self, fake_service: FakeService):
        """Deleting a subscription removes it from the store."""
        result = fake_service.add_subscription("Test Sub", "https://example.com/sub")
        sub_id = result["subscription"]["id"]

        store = fake_service.ensure_store_ready()
        assert any(s["id"] == sub_id for s in store["subscriptions"])

        del_result = fake_service.delete_subscription(sub_id)
        assert del_result["ok"] is True

        store = fake_service.ensure_store_ready()
        assert not any(s["id"] == sub_id for s in store["subscriptions"])

    def test_status_returns_structure(self, fake_service: FakeService):
        """collect_status returns expected fields."""
        status = fake_service.collect_status()
        assert "processes" in status
        assert status["processes"]["xray_alive"] is False
        assert "traffic" in status

    def test_settings_roundtrip(self, fake_service: FakeService):
        """Settings save and load correctly."""
        fake_service.save_settings(file_logs_enabled=True, artifact_retention_days=14)
        settings = fake_service.load_settings()
        assert settings.get("file_logs_enabled") is True
        assert settings.get("artifact_retention_days") == 14

    def test_routing_profile_import_and_activation(self, fake_service: FakeService):
        """Routing profile import and activation work."""
        routing_json = json.dumps({
            "name": "Test Route",
            "direct_sites": ["example.com"],
            "proxy_sites": ["blocked.site"],
            "global_proxy": False,
            "domain_strategy": "AsIs",
        })
        result = fake_service.import_routing_profile(routing_json)
        assert "created" in result
        assert "profile" in result
        store = fake_service.ensure_store_ready()
        profiles = store.get("routing", {}).get("profiles", [])
        assert len(profiles) >= 1
        rp_id = profiles[0]["id"]

        fake_service.activate_routing_profile(rp_id)
        store = fake_service.ensure_store_ready()
        assert store["routing"]["active_profile_id"] == rp_id
        assert store["routing"]["enabled"] is True

        fake_service.clear_active_routing_profile()
        store = fake_service.ensure_store_ready()
        assert store["routing"]["active_profile_id"] is None
        assert store["routing"]["enabled"] is False
