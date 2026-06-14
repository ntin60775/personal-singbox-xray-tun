"""
E2E тесты операций с узлами.
Проверяют: активацию узла, пинг узла, поведение без выбора узла.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import DataTable, Label, TabbedContent

from gui.tui_app import NodesTab, SubvostTUI
from tests.e2e.conftest import FakeService, make_test_app


def _prepare_service(store_dir: Path, project_root: Path) -> FakeService:
    """Создать FakeService с предзаполненной подпиской и узлами."""
    service = FakeService(store_dir=store_dir, project_root=project_root)
    result = service.add_subscription("Test Sub", "https://example.com/sub")
    sub_id = result["subscription"]["id"]
    service.refresh_subscription(sub_id)
    return service


def _make_status_reader(service: FakeService):
    """Вернуть collect_status, читающую active_node из store.

    По умолчанию FakeService.collect_status возвращает None для active_node.
    Эта обёртка подгружает данные из store, чтобы дашборд отображал имя узла.
    """
    orig = service.collect_status

    def patched():
        status = orig()
        try:
            store = service._load_store()
        except Exception:
            return status
        active = store.get("active_selection", {})
        pid = active.get("profile_id")
        nid = active.get("node_id")
        if pid and nid:
            for profile in store.get("profiles", []):
                if profile.get("id") == pid:
                    for node in profile.get("nodes", []):
                        if node.get("id") == nid:
                            status["active_node"] = node
                            return status
        return status

    return patched


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_activate_node(
    temp_store_dir: Path, project_root: Path
):
    """Активация узла: добавить подписку, обновить, выбрать узел,
    нажать btn-activate-node, проверить что дашборд обновился."""
    service = _prepare_service(temp_store_dir, project_root)
    service.collect_status = _make_status_reader(service)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку узлов
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Убедиться что таблица узлов не пуста
        nodes_table = pilot.app.query_one("#nodes-table", DataTable)
        assert nodes_table.row_count > 0, "Таблица узлов пуста после обновления подписки"

        # Получить ключ первой строки
        first = list(nodes_table.ordered_rows)[0]
        row_key = str(first.key.value)

        # Симулировать выбор строки
        nodes_tab = pilot.app.query_one("#nodes-tab", NodesTab)
        nodes_tab.selected_row_key = row_key

        # Нажать активировать
        activate_btn = pilot.app.query_one("#btn-activate-node")
        assert not activate_btn.disabled
        await pilot.click("#btn-activate-node")
        await pilot.pause()
        await pilot.pause()  # дождаться run_in_executor

        # Переключиться на дашборд
        tabs.active = "tab-dashboard"
        await pilot.pause()

        # Проверить что отображается имя узла
        active_label = pilot.app.query_one("#active-node-label", Label)
        label_text = str(active_label.content)
        assert "Node" in label_text or "—" not in label_text, (
            f"Ожидалось имя узла, получено: {label_text}"
        )


async def test_ping_node(
    temp_store_dir: Path, project_root: Path
):
    """Пинг узла: после обновления подписки выбрать узел,
    нажать btn-ping-node, проверить что операция не упала."""
    service = _prepare_service(temp_store_dir, project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку узлов
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        nodes_table = pilot.app.query_one("#nodes-table", DataTable)
        assert nodes_table.row_count > 0

        # Выбрать первую строку
        first = list(nodes_table.ordered_rows)[0]
        row_key = str(first.key.value)
        nodes_tab = pilot.app.query_one("#nodes-tab", NodesTab)
        nodes_tab.selected_row_key = row_key

        # Нажать пинг
        await pilot.click("#btn-ping-node")
        await pilot.pause()
        await pilot.pause()  # дождаться run_in_executor

        # Проверить что приложение живо — делаем переключение вкладки
        tabs.active = "tab-dashboard"
        await pilot.pause()

        # Дашборд отрисован без ошибок
        active_label = pilot.app.query_one("#active-node-label", Label)
        assert active_label is not None


async def test_activate_without_selection(
    temp_store_dir: Path, project_root: Path
):
    """Активация без выбора узла: нажать btn-activate-node,
    убедиться что приложение не упало."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку узлов
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Не выбирать узел — selected_row_key = None
        # Нажать активировать
        await pilot.click("#btn-activate-node")
        await pilot.pause()

        # Приложение не упало, дашборд доступен
        tabs.active = "tab-dashboard"
        await pilot.pause()
        active_label = pilot.app.query_one("#active-node-label", Label)
        assert active_label is not None
