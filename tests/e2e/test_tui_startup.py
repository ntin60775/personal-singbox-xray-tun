"""
E2E тесты запуска TUI-приложения.
Проверяют: отрисовку табов, заголовков, кнопок, начальное состояние.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, DataTable, TabbedContent, TabPane

from tests.e2e.conftest import FakeService, make_test_app


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_app_starts_and_renders_tabs(
    temp_store_dir: Path, project_root: Path
):
    """Приложение запускается, отрисовывает 5 вкладок."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None

        tab_panes = pilot.app.query(TabPane)
        assert len(tab_panes) == 5

        # Проверяем id вкладок
        tab_ids = {tp.id for tp in tab_panes if tp.id}
        expected = {"tab-dashboard", "tab-nodes", "tab-log", "tab-routing", "tab-settings"}
        assert tab_ids == expected, f"Expected tabs {expected}, got {tab_ids}"


async def test_dashboard_shows_initial_state(
    temp_store_dir: Path, project_root: Path
):
    """Дашборд: Старт активен, Стоп неактивен при выключенном VPN."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        start_btn = pilot.app.query_one("#btn-start", Button)
        assert not start_btn.disabled, "Кнопка Старт должна быть активна"

        stop_btn = pilot.app.query_one("#btn-stop", Button)
        assert stop_btn.disabled, "Кнопка Стоп должна быть неактивна"


async def test_nodes_tab_shows_tables(
    temp_store_dir: Path, project_root: Path
):
    """Вкладка Подписки содержит таблицы подписок и узлов."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        sub_table = pilot.app.query_one("#sub-table", DataTable)
        assert sub_table is not None

        nodes_table = pilot.app.query_one("#nodes-table", DataTable)
        assert nodes_table is not None


async def test_routing_tab_shows_controls(
    temp_store_dir: Path, project_root: Path
):
    """Вкладка Маршруты содержит кнопки управления."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-routing"
        await pilot.pause()

        assert pilot.app.query_one("#btn-import-rp", Button) is not None
        assert pilot.app.query_one("#btn-toggle-routing", Button) is not None
        assert pilot.app.query_one("#btn-refresh-geodata", Button) is not None


async def test_settings_tab_loads_values(
    temp_store_dir: Path, project_root: Path
):
    """Вкладка Настройки отображает элементы управления."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)
    service.save_settings(file_logs_enabled=True, artifact_retention_days=30)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-settings"
        await pilot.pause()

        assert pilot.app.query_one("#sw-file-logs") is not None
        assert pilot.app.query_one("#inp-retention") is not None
        assert pilot.app.query_one("#btn-save-settings", Button) is not None
        assert pilot.app.query_one("#btn-cleanup", Button) is not None


async def test_footer_buttons_present(
    temp_store_dir: Path, project_root: Path
):
    """Футер содержит кнопки навигации."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        assert pilot.app.query_one("#btn-footer-refresh", Button) is not None
        assert pilot.app.query_one("#btn-footer-quit", Button) is not None


async def test_tab_switching_no_errors(
    temp_store_dir: Path, project_root: Path
):
    """Переключение всех вкладок не вызывает исключений."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)

        for tab_id in ["tab-dashboard", "tab-nodes", "tab-log", "tab-routing", "tab-settings"]:
            tabs.active = tab_id
            await pilot.pause()
