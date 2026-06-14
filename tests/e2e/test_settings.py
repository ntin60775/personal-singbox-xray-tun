"""
E2E тесты вкладки Настройки TUI-приложения.
Проверяют: сохранение настроек, очистку артефактов.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Switch, TabbedContent

from tests.e2e.conftest import FakeService, make_test_app


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


async def test_save_settings(
    temp_store_dir: Path, project_root: Path
):
    """Изменение настроек и сохранение: переключить Switch, изменить Input,
    нажать Сохранить, проверить что значения записались и загружаются при новом старте."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    # Убедимся что начальные значения — дефолтные
    initial = service.load_settings()
    initial_file_logs = bool(initial.get("file_logs_enabled", False))
    initial_retention = int(initial.get("artifact_retention_days", 7))

    # Выбираем противоположные значения
    new_file_logs = not initial_file_logs
    new_retention = 30 if initial_retention == 7 else 7

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-settings"
        await pilot.pause()

        # Переключаем Switch
        sw = pilot.app.query_one("#sw-file-logs", Switch)
        assert sw is not None
        await pilot.click("#sw-file-logs")
        await pilot.pause()
        assert sw.value == new_file_logs, (
            f"Switch должен быть {new_file_logs}, а он {sw.value}"
        )

        # Изменяем Input retention
        inp = pilot.app.query_one("#inp-retention", Input)
        assert inp is not None
        await pilot.click("#inp-retention")
        await pilot.press("end", "shift+home", "delete")
        await pilot.press("3", "0")
        assert inp.value == str(new_retention), (
            f"Retention должен быть {new_retention}, а он {inp.value}"
        )

        # Нажимаем Сохранить
        save_btn = pilot.app.query_one("#btn-save-settings", Button)
        assert not save_btn.disabled
        await pilot.click("#btn-save-settings")
        await pilot.pause()
        await pilot.pause()

        # Проверяем через service что значения записались
        settings = service.load_settings()
        assert settings.get("file_logs_enabled") == new_file_logs, (
            f"service: file_logs_enabled должен быть {new_file_logs}, "
            f"а он {settings.get('file_logs_enabled')}"
        )
        assert settings.get("artifact_retention_days") == new_retention, (
            f"service: artifact_retention_days должен быть {new_retention}, "
            f"а он {settings.get('artifact_retention_days')}"
        )

    # Перезапускаем приложение с тем же service — проверяем что настройки загрузились
    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-settings"
        await pilot.pause()

        sw = pilot.app.query_one("#sw-file-logs", Switch)
        assert sw.value == new_file_logs, (
            f"После перезапуска Switch должен быть {new_file_logs}, "
            f"а он {sw.value}"
        )

        inp = pilot.app.query_one("#inp-retention", Input)
        assert inp.value == str(new_retention), (
            f"После перезапуска retention должен быть {new_retention}, "
            f"а он {inp.value}"
        )


async def test_cleanup_artifacts(
    temp_store_dir: Path, project_root: Path
):
    """Нажатие кнопки Очистить артефакты не вызывает исключений."""
    service = FakeService(store_dir=temp_store_dir, project_root=project_root)

    async with make_test_app(service).run_test() as pilot:
        await pilot.pause()

        tabs = pilot.app.query_one(TabbedContent)
        tabs.active = "tab-settings"
        await pilot.pause()

        cleanup_btn = pilot.app.query_one("#btn-cleanup", Button)
        assert cleanup_btn is not None
        assert not cleanup_btn.disabled

        # Нажимаем очистку — операция не должна упасть
        await pilot.click("#btn-cleanup")
        await pilot.pause()
        await pilot.pause()

        # Если дошли сюда — исключения не было
        assert True
