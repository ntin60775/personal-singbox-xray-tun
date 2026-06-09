"""Инфраструктурный слой — адаптеры JSON-хранилища."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Проект использует плоский импорт из gui/ — обеспечиваем его
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gui.domain import (
    Node,
    Profile,
    RoutingProfile,
    Subscription,
    node_from_store_dict,
    node_to_store_dict,
    profile_from_store_dict,
    profile_to_store_dict,
    routing_profile_from_store_dict,
    subscription_from_store_dict,
    subscription_to_store_dict,
)

import subvost_store as _store


class JsonStoreAdapter:
    """Прямой доступ к сырому store для операций, ещё не обёрнутых в репозитории."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    @property
    def raw(self) -> dict[str, Any]:
        return self._store


class JsonNodeRepository:
    """Реализация NodeRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    def get_active(self) -> Node | None:
        profile_dict, node_dict = _store.get_active_node(self._store)
        if node_dict is None:
            return None
        node = node_from_store_dict(node_dict)
        node.profile_id = profile_dict["id"] if profile_dict else ""
        return node

    def get_by_id(self, profile_id: str, node_id: str) -> Node | None:
        profile_dict = _store._find_profile(self._store, profile_id)
        if profile_dict is None:
            return None
        for nd in profile_dict.get("nodes", []):
            if nd.get("id") == node_id:
                node = node_from_store_dict(nd)
                node.profile_id = profile_id
                return node
        return None

    def save(self, profile_id: str, node: Node) -> None:
        node.profile_id = profile_id
        record = node_to_store_dict(node)
        profile = _store._find_profile(self._store, profile_id)
        if profile is None:
            raise ValueError(f"Профиль {profile_id} не найден")
        nodes = profile.setdefault("nodes", [])
        for i, existing in enumerate(nodes):
            if existing.get("id") == node.id:
                nodes[i] = record
                return
        nodes.append(record)

    def delete(self, profile_id: str, node_id: str) -> None:
        profile = _store._find_profile(self._store, profile_id)
        if profile is None:
            return
        profile["nodes"] = [n for n in profile.get("nodes", []) if n.get("id") != node_id]

    def activate(self, profile_id: str, node_id: str) -> None:
        _store.activate_selection(self._store, profile_id, node_id, source="ui")


class JsonProfileRepository:
    """Реализация ProfileRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    def get_all(self) -> list[Profile]:
        result: list[Profile] = []
        for pd in self._store.get("profiles", []):
            profile = profile_from_store_dict(pd)
            result.append(profile)
        return result

    def get_by_id(self, profile_id: str) -> Profile | None:
        for pd in self._store.get("profiles", []):
            if pd.get("id") == profile_id:
                return profile_from_store_dict(pd)
        return None

    def save(self, profile: Profile) -> None:
        record = profile_to_store_dict(profile)
        profiles = self._store.setdefault("profiles", [])
        for i, existing in enumerate(profiles):
            if existing.get("id") == profile.id:
                profiles[i] = record
                return
        profiles.append(record)

    def delete(self, profile_id: str) -> None:
        _store.delete_profile(self._store, profile_id)


class JsonSubscriptionRepository:
    """Реализация SubscriptionRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    def get_all(self) -> list[Subscription]:
        return [
            subscription_from_store_dict(sd)
            for sd in self._store.get("subscriptions", [])
        ]

    def get_by_id(self, subscription_id: str) -> Subscription | None:
        for sd in self._store.get("subscriptions", []):
            if sd.get("id") == subscription_id:
                return subscription_from_store_dict(sd)
        return None

    def save(self, sub: Subscription) -> None:
        record = subscription_to_store_dict(sub)
        subs = self._store.setdefault("subscriptions", [])
        for i, existing in enumerate(subs):
            if existing.get("id") == sub.id:
                subs[i] = record
                return
        subs.append(record)

    def delete(self, subscription_id: str) -> None:
        _store.delete_subscription(self._store, subscription_id)


class JsonRoutingRepository:
    """Реализация RoutingRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]):
        self._store = store

    def get_active(self) -> RoutingProfile | None:
        rp_dict = _store.get_active_routing_profile(self._store)
        if rp_dict is None:
            return None
        return routing_profile_from_store_dict(rp_dict)

    def get_all(self) -> list[RoutingProfile]:
        return [
            routing_profile_from_store_dict(rd)
            for rd in self._store.get("routing", {}).get("profiles", [])
        ]

    def get_by_id(self, profile_id: str) -> RoutingProfile | None:
        for rd in self._store.get("routing", {}).get("profiles", []):
            if rd.get("id") == profile_id:
                return routing_profile_from_store_dict(rd)
        return None

    def save(self, rp: RoutingProfile) -> None:
        # Routing profiles don't have a direct save function — mutate the list
        routing = self._store.setdefault("routing", {})
        profiles: list[dict[str, Any]] = routing.setdefault("profiles", [])
        record = _routing_profile_to_store_dict(rp)
        for i, existing in enumerate(profiles):
            if existing.get("id") == rp.id:
                profiles[i] = record
                return
        profiles.append(record)

    def activate(self, profile_id: str) -> None:
        self._store.setdefault("routing", {})["active_profile_id"] = profile_id

    def deactivate(self) -> None:
        self._store.setdefault("routing", {})["active_profile_id"] = None


# ── Вспомогательные ─────────────────────────────────────────────────

def _routing_profile_to_store_dict(rp: RoutingProfile) -> dict[str, Any]:
    """Сериализация RoutingProfile в store-запись (обратная фабрике)."""
    return {
        "id": rp.id,
        "name": rp.name,
        "name_key": rp.name_key,
        "enabled": rp.enabled,
        "auto_managed": rp.auto_managed,
        "source_kind": rp.source_kind,
        "source_format": rp.source_format,
        "activation_mode": rp.activation_mode,
        "global_proxy": rp.global_proxy,
        "domain_strategy": rp.domain_strategy,
        "geoip_url": rp.geoip_url,
        "geosite_url": rp.geosite_url,
        "direct_sites": rp.direct_sites,
        "direct_ip": rp.direct_ip,
        "proxy_sites": rp.proxy_sites,
        "proxy_ip": rp.proxy_ip,
        "block_sites": rp.block_sites,
        "block_ip": rp.block_ip,
        "dns_hosts": rp.dns_hosts,
        "route_order": rp.route_order,
        "source_subscription_id": rp.source_subscription_id,
        "provider_id": rp.provider_id,
        "created_at": rp.created_at,
        "updated_at": rp.updated_at,
    }
