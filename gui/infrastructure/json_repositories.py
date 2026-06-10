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
    Subscription,
    node_from_store_dict,
    node_to_store_dict,
    subscription_from_store_dict,
    subscription_to_store_dict,
)

import subvost_store as _store


class JsonNodeRepository:
    """Реализация NodeRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]) -> None:
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


class JsonSubscriptionRepository:
    """Реализация SubscriptionRepository поверх subvost_store."""

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def get_all(self) -> list[Subscription]:
        """Получить все подписки."""
        return [
            subscription_from_store_dict(s)
            for s in (self._store.get("subscriptions") or [])
        ]

    def get_by_id(self, sub_id: str) -> Subscription | None:
        """Найти подписку по id."""
        for s in self._store.get("subscriptions") or []:
            if s.get("id") == sub_id:
                return subscription_from_store_dict(s)
        return None

    def save(self, sub: Subscription) -> None:
        """Сохранить или обновить подписку."""
        subs = self._store.setdefault("subscriptions", [])
        for i, s in enumerate(subs):
            if s.get("id") == sub.id:
                subs[i] = subscription_to_store_dict(sub)
                return
        subs.append(subscription_to_store_dict(sub))

    def delete(self, sub_id: str) -> None:
        """Удалить подписку."""
        self._store["subscriptions"] = [
            s for s in (self._store.get("subscriptions") or [])
            if s.get("id") != sub_id
        ]

    def add_subscription(self, name: str, url: str) -> Subscription:
        """Добавить новую подписку и вернуть созданную сущность."""
        return _store.add_subscription(self._store, name, url)
