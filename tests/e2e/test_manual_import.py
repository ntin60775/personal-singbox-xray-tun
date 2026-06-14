"""E2E тесты ручного импорта узлов через ImportLinkModal."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import DataTable, TabbedContent, TextArea

from tests.e2e.conftest import FakeService, make_test_app

VLESS_LINK = (
    "vless://12345678-1234-1234-1234-123456789abc"
    "@1.2.3.4:443"
    "?encryption=none&security=reality"
    "&flow=xtls-rprx-vision&sni=yahoo.com"
    "&fp=chrome&pbk=test-public-key&sid=abcd&type=tcp"
    "#TestNode"
)


async def test_manual_import_modal(
    temp_store_dir: Path, project_root: Path
) -> None:
    """Открыть модал импорта ссылок, вставить vless-ссылку, импортировать,
    проверить что узел появился в таблице."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку Подписки
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Нажать кнопку "Добавить вручную" — откроется ImportLinkModal
        await pilot.click("#btn-add-manual")
        await pilot.pause()
        await pilot.pause()  # дать модалу отрисоваться

        # Модал — текущий экран; виджеты модала ищем через app.screen
        ta = pilot.app.screen.query_one("#ta-links", TextArea)
        assert ta is not None

        # Ввести vless-ссылку
        ta.text = VLESS_LINK
        await pilot.pause()
        assert ta.text == VLESS_LINK

        # Нажать Импорт
        await pilot.click("#btn-link-import")
        await pilot.pause()
        await pilot.pause()  # дождаться завершения run_in_executor + скрытия LoadingModal

        table = pilot.app.query_one("#nodes-table", DataTable)
        assert table.row_count > 0, "Таблица узлов пуста после импорта"

        rows = list(table.ordered_rows)
        node_names = [str(table.get_row(r.key)[0]) for r in rows]
        assert "TestNode" in node_names, (
            f"Узел 'TestNode' не найден в таблице. Имена: {node_names}"
        )


async def test_manual_import_empty(
    temp_store_dir: Path, project_root: Path
) -> None:
    """Открыть модал, оставить TextArea пустым, нажать Импорт,
    проверить что приложение не упало."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку Подписки
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Нажать кнопку "Добавить вручную"
        await pilot.click("#btn-add-manual")
        await pilot.pause()
        await pilot.pause()

        # Убедиться что TextArea пуст (через screen — модал активен)
        ta = pilot.app.screen.query_one("#ta-links", TextArea)
        assert ta.text == ""

        # Нажать Импорт с пустым содержимым
        await pilot.click("#btn-link-import")
        await pilot.pause()
        await pilot.pause()

        # Приложение не упало — проверяем что таблицы существуют
        sub_table = pilot.app.query_one("#sub-table", DataTable)
        nodes_table = pilot.app.query_one("#nodes-table", DataTable)
        assert sub_table is not None
        assert nodes_table is not None
