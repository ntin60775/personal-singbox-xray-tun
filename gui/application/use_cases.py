"""Use Cases — сценарии прикладного слоя.

Каждый use case — dataclass с внедрёнными портами (репозиториями, адаптерами).
Метод `execute()` выполняет сценарий, возвращает результат.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Обеспечиваем плоский импорт из gui/
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gui.domain import Node, Profile, Subscription
from .ports import NodeRepository, ProfileRepository, SubscriptionRepository


# ── Результаты use cases ────────────────────────────────────────────

@dataclass
class StartRuntimeResult:
    success: bool
    message: str = ""
    pid: int | None = None


@dataclass
class StopRuntimeResult:
    success: bool
    message: str = ""


@dataclass
class ImportSubscriptionResult:
    success: bool
    subscription_id: str = ""
    node_count: int = 0
    message: str = ""


@dataclass
class CollectStatusResult:
    """Read-model: все данные для UI."""
    data: dict[str, Any]  # сырой status dict — пока делегируем сервису


@dataclass
class PingNodeResult:
    success: bool
    node_id: str = ""
    latency_ms: float | None = None
    error: str = ""


# ── Use Cases ───────────────────────────────────────────────────────

@dataclass
class ActivateNodeUseCase:
    """Выбор активного узла."""
    node_repo: NodeRepository
    profile_repo: ProfileRepository

    def execute(self, profile_id: str, node_id: str) -> Node:
        profile = self.profile_repo.get_by_id(profile_id)
        if profile is None:
            raise ValueError(f"Профиль {profile_id} не найден")
        node = profile.activate_node(node_id)
        self.node_repo.activate(profile_id, node_id)
        return node


@dataclass
class ListNodesUseCase:
    """Получить список узлов профиля."""
    profile_repo: ProfileRepository

    def execute(self, profile_id: str | None = None) -> list[Node]:
        if profile_id:
            profile = self.profile_repo.get_by_id(profile_id)
            if profile is None:
                return []
            return profile.nodes
        all_nodes: list[Node] = []
        for profile in self.profile_repo.get_all():
            all_nodes.extend(profile.nodes)
        return all_nodes


@dataclass
class ListProfilesUseCase:
    """Получить список профилей."""
    profile_repo: ProfileRepository

    def execute(self) -> list[Profile]:
        return self.profile_repo.get_all()


@dataclass
class ListSubscriptionsUseCase:
    """Получить список подписок."""
    subscription_repo: SubscriptionRepository

    def execute(self) -> list[Subscription]:
        return self.subscription_repo.get_all()


@dataclass
class GetActiveNodeUseCase:
    """Получить текущий активный узел."""
    node_repo: NodeRepository

    def execute(self) -> Node | None:
        return self.node_repo.get_active()
