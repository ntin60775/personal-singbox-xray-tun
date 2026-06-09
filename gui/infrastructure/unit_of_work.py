"""Unit of Work — координация загрузки/сохранения store с доменными типами."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Обеспечиваем плоский импорт из gui/
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import subvost_store as _store

from .json_repositories import (
    JsonNodeRepository,
    JsonProfileRepository,
    JsonRoutingRepository,
    JsonStoreAdapter,
    JsonSubscriptionRepository,
)


@dataclass
class StoreUnitOfWork:
    """Загружает store, предоставляет репозитории, атомарно сохраняет при коммите.

    Использование:
        uow = StoreUnitOfWork(paths, project_root, uid, gid)
        with uow:
            node = uow.nodes.get_active()
            uow.nodes.save("prof-1", updated_node)
        # commit вызван автоматически при выходе из with
    """

    paths: Any  # AppPaths
    project_root: Path
    uid: int | None = None
    gid: int | None = None

    _store: dict[str, Any] | None = field(default=None, init=False)
    _nodes: JsonNodeRepository | None = field(default=None, init=False)
    _profiles: JsonProfileRepository | None = field(default=None, init=False)
    _subscriptions: JsonSubscriptionRepository | None = field(default=None, init=False)
    _routing: JsonRoutingRepository | None = field(default=None, init=False)
    _adapter: JsonStoreAdapter | None = field(default=None, init=False)
    _committed: bool = field(default=False, init=False)
    _rolled_back: bool = field(default=False, init=False)

    @property
    def nodes(self) -> JsonNodeRepository:
        if self._nodes is None:
            raise RuntimeError("UnitOfWork не открыт. Используйте 'with uow:'")
        return self._nodes

    @property
    def profiles(self) -> JsonProfileRepository:
        if self._profiles is None:
            raise RuntimeError("UnitOfWork не открыт.")
        return self._profiles

    @property
    def subscriptions(self) -> JsonSubscriptionRepository:
        if self._subscriptions is None:
            raise RuntimeError("UnitOfWork не открыт.")
        return self._subscriptions

    @property
    def routing(self) -> JsonRoutingRepository:
        if self._routing is None:
            raise RuntimeError("UnitOfWork не открыт.")
        return self._routing

    @property
    def raw(self) -> JsonStoreAdapter:
        if self._adapter is None:
            raise RuntimeError("UnitOfWork не открыт.")
        return self._adapter

    def __enter__(self) -> StoreUnitOfWork:
        if self._store is not None:
            raise RuntimeError("UnitOfWork уже открыт")
        if _store_is_initialized(self.paths):
            self._store = _store.load_store(self.paths)
        else:
            self._store = _store.ensure_store_initialized(
                self.paths, self.project_root, uid=self.uid, gid=self.gid
            )
        self._nodes = JsonNodeRepository(self._store)
        self._profiles = JsonProfileRepository(self._store)
        self._subscriptions = JsonSubscriptionRepository(self._store)
        self._routing = JsonRoutingRepository(self._store)
        self._adapter = JsonStoreAdapter(self._store)
        self._committed = False
        self._rolled_back = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._rolled_back = True
            return  # не сохраняем при исключении
        self.commit()

    def commit(self) -> None:
        """Атомарно сохранить store на диск."""
        if self._store is None:
            raise RuntimeError("UnitOfWork не открыт")
        if self._rolled_back:
            raise RuntimeError("Нельзя commit после rollback")
        if self._committed:
            return
        _store.save_store(self.paths, self._store, uid=self.uid, gid=self.gid)
        self._committed = True

    def rollback(self) -> None:
        """Откатить изменения (не сохранять)."""
        self._rolled_back = True


def _store_is_initialized(paths: Any) -> bool:
    """Проверяет, существует ли store-файл на диске."""
    try:
        return paths.store_file.exists()
    except Exception:
        return False
