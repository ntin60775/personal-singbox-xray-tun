"""Доменные события — фиксация значимых изменений состояния."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RuntimeStarted:
    """VPN-подключение установлено."""
    profile_id: str
    node_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class RuntimeStopped:
    """VPN-подключение остановлено."""
    stopped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class NodeActivated:
    """Выбран активный узел."""
    node_id: str
    profile_id: str
    activated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class SubscriptionImported:
    """Подписка успешно импортирована."""
    subscription_id: str
    node_count: int
    imported_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class SubscriptionRefreshed:
    """Подписка обновлена (новые данные получены)."""
    subscription_id: str
    new_nodes: int
    updated_nodes: int
    status: str  # "ok" | "not_modified"
    refreshed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class RoutingProfileActivated:
    """Активирован routing-профиль."""
    profile_id: str
    activated_at: str = field(default_factory=lambda: datetime.now().isoformat())
