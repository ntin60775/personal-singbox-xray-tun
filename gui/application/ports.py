"""Порты (интерфейсы) прикладного слоя — протоколы для репозиториев."""
from __future__ import annotations

from typing import Any, Protocol

from gui.domain import Node, Profile, RoutingProfile, Subscription


# ── Репозитории ─────────────────────────────────────────────────────

class NodeRepository(Protocol):
    """Чтение и запись узлов."""

    def get_active(self) -> Node | None:
        """Получить активный узел (выбранный пользователем)."""
        ...

    def get_by_id(self, profile_id: str, node_id: str) -> Node | None:
        """Получить узел по id в рамках профиля."""
        ...

    def save(self, profile_id: str, node: Node) -> None:
        """Сохранить или обновить узел."""
        ...

    def delete(self, profile_id: str, node_id: str) -> None:
        """Удалить узел."""
        ...

    def activate(self, profile_id: str, node_id: str) -> None:
        """Активировать узел (сохранить выбор)."""
        ...


class ProfileRepository(Protocol):
    """Управление профилями."""

    def get_all(self) -> list[Profile]:
        """Все профили."""
        ...

    def get_by_id(self, profile_id: str) -> Profile | None:
        """Профиль по id."""
        ...

    def save(self, profile: Profile) -> None:
        """Сохранить или обновить профиль."""
        ...

    def delete(self, profile_id: str) -> None:
        """Удалить профиль."""
        ...


class SubscriptionRepository(Protocol):
    """Управление подписками."""

    def get_all(self) -> list[Subscription]:
        """Все подписки."""
        ...

    def get_by_id(self, subscription_id: str) -> Subscription | None:
        """Подписка по id."""
        ...

    def save(self, sub: Subscription) -> None:
        """Сохранить или обновить подписку."""
        ...

    def delete(self, subscription_id: str) -> None:
        """Удалить подписку."""
        ...


class RoutingRepository(Protocol):
    """Управление routing-профилями."""

    def get_active(self) -> RoutingProfile | None:
        """Активный routing-профиль."""
        ...

    def get_all(self) -> list[RoutingProfile]:
        """Все routing-профили."""
        ...

    def get_by_id(self, profile_id: str) -> RoutingProfile | None:
        """Routing-профиль по id."""
        ...

    def save(self, rp: RoutingProfile) -> None:
        """Сохранить или обновить routing-профиль."""
        ...

    def activate(self, profile_id: str) -> None:
        """Активировать routing-профиль."""
        ...

    def deactivate(self) -> None:
        """Деактивировать текущий routing-профиль."""
        ...


class StorePort(Protocol):
    """Порт для загрузки и сохранения всего store."""

    def load(self) -> dict[str, Any]:
        """Загрузить store как сырой dict."""
        ...

    def save(self, store: dict[str, Any]) -> None:
        """Атомарно сохранить store."""
        ...

    def is_initialized(self) -> bool:
        """Существует ли store-файл на диске."""
        ...

    def initialize(self) -> dict[str, Any]:
        """Создать и сохранить новый store с defaults."""
        ...
