"""
E2E тесты на обработку ошибочных сценариев.
Проверяют: двойное нажатие старт, стоп без запуска, пустой URL подписки,
длинное имя подписки.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, TabbedContent
from tests.e2e.conftest import FakeService, make_test_app


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_double_click_start(temp_store_dir: Path, project_root: Path):
    """Двойное нажатие #btn-start не вызывает падения приложения."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Два быстрых нажатия на Старт
        await pilot.click("#btn-start")
        await pilot.pause()
        await pilot.click("#btn-start")
        await pilot.pause()

        # Приложение должно остаться живым
        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_stop_when_not_running(temp_store_dir: Path, project_root: Path):
    """Нажатие #btn-stop без активного подключения не вызывает падения."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Кнопка Стоп неактивна (xray_alive=False), но нажатие не должно ломать приложение
        await pilot.click("#btn-stop")
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None


async def test_empty_subscription_url(temp_store_dir: Path, project_root: Path):
    """Попытка добавить подписку с пустым URL не вызывает падения."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку Подписки
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Открыть модал импорта подписки
        await pilot.click("#btn-import-sub")
        await pilot.pause()

        # Оба поля пустые — нажать Добавить (модал проверяет name и url, возвращает None)
        await pilot.click("#btn-sub-add")
        await pilot.pause()

        # Приложение живо, модал остался открыт
        tabs = pilot.app.query_one(TabbedContent)
        assert tabs is not None

        # Закрыть модал через Отмена
        await pilot.click("#btn-sub-cancel")
        await pilot.pause()


async def test_very_long_subscription_name(temp_store_dir: Path, project_root: Path):
    """Импорт подписки с именем из 200 символов успешно добавляется."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)
    long_name = "A" * 200
    url = "https://example.com/sub"

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключиться на вкладку Подписки
        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-nodes"
        await pilot.pause()

        # Открыть модал импорта подписки
        await pilot.click("#btn-import-sub")
        await pilot.pause()

        # Ввести имя (200 символов) — поля в модальном окне
        modal_screen = pilot.app.screen
        name_input = modal_screen.query_one("#inp-sub-name", Input)
        name_input.value = long_name

        url_input = modal_screen.query_one("#inp-sub-url", Input)
        url_input.value = url

        # Нажать Добавить
        await pilot.click("#btn-sub-add")
        # Ждать закрытия модала и завершения executor-операции
        await pilot.pause()
        await pilot.pause()
        # Проверить что подписка появилась в таблице
        sub_table = pilot.app.query_one("#sub-table", DataTable)
        assert sub_table.row_count > 0, "Таблица подписок пуста после импорта"

        # Проверить что подписка добавилась в store
        store = service._load_store()
        sub_names = [s.get("name", "") for s in store.get("subscriptions", [])]
        assert long_name in sub_names, (
            f"Подписка с именем длиной {len(long_name)} символов не найдена в store"
        )
