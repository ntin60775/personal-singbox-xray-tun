"""
E2E тесты управления маршрутизацией.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, DataTable, TabbedContent, TextArea

from tests.e2e.conftest import FakeService, make_test_app

ROUTING_JSON = (
    '{"name": "Test", "direct_sites": ["example.com"], '
    '"proxy_sites": ["blocked.site"], "global_proxy": false, '
    '"domain_strategy": "AsIs", '
    '"geoipurl": "local", "geositeurl": "local"}'
)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_import_routing_profile(
    temp_store_dir: Path, project_root: Path
) -> None:
    """Импорт routing-профиля через модальное окно."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключаемся на вкладку Маршруты
        tabs = pilot.app.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-routing"
        await pilot.pause()

        # Открываем модал импорта
        await pilot.click("#btn-import-rp")
        await pilot.pause()
        await pilot.pause()

        # Заполняем JSON в TextArea напрямую
        ta = pilot.app.screen.query_one("#ta-rp", TextArea)
        ta.text = ROUTING_JSON

        # Нажимаем Импорт и ждём завершения операции
        await pilot.click("#btn-rp-import")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # _update_routing() использует self._store (снимок на момент _update_nodes()).
        # Обновляем кэш и перерисовываем таблицу.
        pilot.app._store = service._load_store()
        pilot.app._update_routing()
        await pilot.pause()

        # Проверяем, что профиль появился в таблице
        rt = pilot.app.query_one("#routing-table", DataTable)
        assert rt.row_count == 1, f"Ожидался 1 профиль, получено {rt.row_count}"
        row_data = rt.get_row_at(0)
        assert row_data[0] == "Test", (
            f"Ожидалось имя 'Test', получено '{row_data[0]}'"
        )


async def test_activate_routing_profile(
    temp_store_dir: Path, project_root: Path
) -> None:
    """Активация routing-профиля после импорта."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    # Импортируем профиль через сервис перед запуском TUI
    service.import_routing_profile(ROUTING_JSON)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключаемся на вкладку Маршруты
        tabs = pilot.app.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-routing"
        await pilot.pause()

        # _store уже загружен _update_nodes() при on_mount.
        # Явно обновляем отображение таблицы маршрутов.
        pilot.app._store = service._load_store()
        pilot.app._update_routing()
        await pilot.pause()

        # Выбираем профиль в таблице
        rt = pilot.app.query_one("#routing-table", DataTable)
        assert rt.row_count > 0, "Нет профилей для активации"
        rt.move_cursor(row=0, column=0)
        await pilot.pause()

        # Нажимаем Активировать профиль
        await pilot.click("#btn-activate-rp")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # Проверяем, что профиль активирован (через store)
        store = service._load_store()
        active_id = store["routing"]["active_profile_id"]
        assert active_id is not None, "Профиль не активирован"

        # Перерисовываем и проверяем, что профиль всё ещё в таблице
        pilot.app._update_routing()
        await pilot.pause()
        rows = list(rt.ordered_rows)
        assert len(rows) == 1, f"Ожидался 1 профиль, получено {len(rows)}"


async def test_toggle_routing(
    temp_store_dir: Path, project_root: Path
) -> None:
    """Включение/выключение маршрутизации."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    # Импортируем профиль перед тестом, иначе ensure_store_structure
    # сбрасывает enabled=False при сохранении (нет профилей в routing.profiles).
    service.import_routing_profile(ROUTING_JSON)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        # Переключаемся на вкладку Маршруты
        tabs = pilot.app.query_one("#main-tabs", TabbedContent)
        tabs.active = "tab-routing"
        await pilot.pause()

        # Запоминаем текущее состояние
        store = service._load_store()
        initial_state = bool(store.get("routing", {}).get("enabled", False))

        # Нажимаем кнопку переключения маршрутизации
        await pilot.click("#btn-toggle-routing")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # Проверяем, что состояние изменилось
        store = service._load_store()
        new_state = bool(store.get("routing", {}).get("enabled", False))
        assert new_state != initial_state, (
            f"Состояние маршрутизации не изменилось "
            f"(было {initial_state}, стало {new_state})"
        )
