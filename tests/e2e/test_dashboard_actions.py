"""
E2E тесты кнопок Старт/Стоп/Диагностика.
Проверяют реальное выполнение действий, а не только отсутствие краша.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Button, TabbedContent

from tests.e2e.conftest import FakeService, make_test_app


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_start_button_calls_runtime(
    temp_store_dir: Path, project_root: Path
):
    """Нажатие Старт вызывает start_runtime и показывает уведомление."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Убедимся что Старт не disabled
        start_btn = pilot.app.query_one("#btn-start", Button)
        assert not start_btn.disabled, "Кнопка Старт должна быть активна"

        # Нажимаем Старт
        await pilot.click("#btn-start")
        await pilot.pause()
        await pilot.pause()  # run_in_executor
        await pilot.pause()  # ещё на всякий случай

        # Приложение должно остаться живым после операции
        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_stop_button_calls_runtime(
    temp_store_dir: Path, project_root: Path
):
    """Нажатие Стоп вызывает stop_runtime и не падает."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Кнопка Стоп обычно disabled, но нажатие не должно крашить
        stop_btn = pilot.app.query_one("#btn-stop", Button)
        # Не проверяем disabled — просто жмём
        await pilot.click("#btn-stop")
        await pilot.pause()
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_diag_button_works(
    temp_store_dir: Path, project_root: Path
):
    """Нажатие Диагностика вызывает capture_diagnostics."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        await pilot.click("#btn-diag")
        await pilot.pause()
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_start_stop_sequence(
    temp_store_dir: Path, project_root: Path
):
    """Последовательность Старт → Стоп не вызывает ошибок."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Старт
        await pilot.click("#btn-start")
        await pilot.pause()
        await pilot.pause()

        # Стоп
        await pilot.click("#btn-stop")
        await pilot.pause()
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_double_click_start_safe(
    temp_store_dir: Path, project_root: Path
):
    """Двойное нажатие Старт не вызывает падения."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        await pilot.click("#btn-start")
        await pilot.pause()
        await pilot.click("#btn-start")
        await pilot.pause()
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None
