#!/usr/bin/env python3
"""Универсальный TUI-фронт Subvost Xray TUN на textual."""
from __future__ import annotations

import asyncio
import atexit
import os
import subprocess
import sys
import threading
import signal
import datetime
import traceback
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

# Импортируем бизнес-логику напрямую
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from subvost_app_service import (
    SubvostAppService,
    build_default_service,
)
from subvost_parser import preview_links
from subvost_store import save_manual_import_results, store_payload


from subvost_paths import APP_DIRNAME, resolve_config_home
from gui.presentation.view_models import build_view_model, humanize_bytes as _humanize_bytes, humanize_rate as _humanize_rate
from infrastructure.adapters import ShellRuntimeAdapter, SystemNetworkAdapter
from infrastructure.json_repositories import JsonNodeRepository, JsonRoutingRepository, JsonSubscriptionRepository

TUI_LOCK_PATH = PROJECT_ROOT / ".subvost" / "tui.lock"


def _cleanup_tui_lock() -> None:
    """Удаляет lock-файл TUI при выходе, если он принадлежит текущему процессу."""
    try:
        if TUI_LOCK_PATH.exists():
            lines = TUI_LOCK_PATH.read_text().strip().split("\n")
            if len(lines) >= 1:
                lock_pid = int(lines[0].strip())
                if lock_pid == os.getpid():
                    TUI_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


OLD_TUI_LOCK_PATH = resolve_config_home(Path.home()) / APP_DIRNAME / "tui.lock"


def _migrate_old_lock() -> None:
    """Удаляет старый общий lock-файл из ~/.config (миграция на per-bundle lock)."""
    try:
        OLD_TUI_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _write_tui_lock() -> None:
    """Записывает lock-файл с PID и PROJECT_ROOT текущего процесса (атомарно)."""
    from subvost_paths import atomic_write_text
    TUI_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(TUI_LOCK_PATH, f"{os.getpid()}\n{PROJECT_ROOT}", mode=0o644)


TUI_APP_ID = "io.subvost.XrayTun.TUI"
TUI_TITLE = "Subvost Xray TUN"


def _run_in_thread(func, *args, **kwargs):
    """Запускает функцию в потоке и возвращает результат через future."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(func, *args, **kwargs).result()


class LoadingModal(ModalScreen):
    """Модальный экран загрузки с сообщением."""

    BINDINGS = [("escape", "dismiss_loading", "Закрыть")]

    def __init__(self, message: str = "Выполнение...") -> None:
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="loading-container"):
            yield Label(self.message, id="loading-label")

    def action_dismiss_loading(self) -> None:
        self.dismiss(False)

class ConfirmModal(ModalScreen):
    """Модальный экран подтверждения."""

    BINDINGS = [("y", "confirm", "Да"), ("n", "dismiss", "Нет"), ("escape", "dismiss", "Отмена")]

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="confirm-container"):
            yield Label(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Да", variant="success", id="confirm-yes")
                yield Button("Нет", variant="error", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

class TuiLockConflictModal(ModalScreen):
    """Диалог при конфликте lock: другой TUI уже запущен из этого bundle."""

    BINDINGS = [
        ("r", "replace", "Заменить"),
        ("escape", "dismiss", "Отмена"),
        ("к", "replace", ""),
    ]

    def __init__(self, lock_pid: int, lock_root: str) -> None:
        self.lock_pid = lock_pid
        self.lock_root = lock_root
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="lock-conflict-container"):
            yield Static("[b]TUI уже запущен[/b]", classes="title")
            yield Static(f"Процесс PID {self.lock_pid} из")
            yield Static(f"{self.lock_root}")
            yield Static("")
            yield Static("Выберите действие:")
            with Horizontal(id="lock-conflict-buttons"):
                yield Button(
                    "Заменить (закрыть старый, открыть новый)",
                    variant="warning",
                    id="btn-lock-replace",
                )
                yield Button(
                    "Отмена (работать в старом окне)",
                    variant="primary",
                    id="btn-lock-cancel",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-lock-replace":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_replace(self) -> None:
        self.dismiss(True)



class ImportSubscriptionModal(ModalScreen):
    """Модальный диалог импорта подписки."""

    BINDINGS = [("escape", "dismiss", "Отмена")]

    def compose(self) -> ComposeResult:
        with Container(id="import-sub-container"):
            yield Static("[b]Импорт подписки[/b]", classes="title")
            yield Label("Название:")
            yield Input(placeholder="Название подписки", id="inp-sub-name")
            yield Label("URL:")
            yield Input(placeholder="https://", id="inp-sub-url")
            with Horizontal(id="import-sub-buttons"):
                yield Button("Добавить", variant="success", id="btn-sub-add")
                yield Button("Отмена", variant="error", id="btn-sub-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sub-add":
            name = self.query_one("#inp-sub-name", Input).value.strip()
            url = self.query_one("#inp-sub-url", Input).value.strip()
            if not name or not url:
                return
            self.dismiss({"name": name, "url": url})
        else:
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)


class ImportLinkModal(ModalScreen):
    """Модальный диалог импорта ссылок."""

    BINDINGS = [("escape", "dismiss", "Отмена")]

    def compose(self) -> ComposeResult:
        with Container(id="import-link-container"):
            yield Static("[b]Импорт ссылок[/b]", classes="title")
            yield Label("Вставьте ссылки (по одной на строку):")
            yield TextArea(id="ta-links")
            with Horizontal(id="import-link-buttons"):
                yield Button("Импортировать", variant="success", id="btn-link-import")
                yield Button("Отмена", variant="error", id="btn-link-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-link-import":
            text = self.query_one("#ta-links", TextArea).text
            self.dismiss({"text": text, "activate_single": False})
        else:
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)


class ImportRoutingProfileModal(ModalScreen):
    """Модальный диалог импорта routing-профиля."""

    BINDINGS = [("escape", "dismiss", "Отмена")]

    def compose(self) -> ComposeResult:
        with Container(id="import-rp-container"):
            yield Static("[b]Импорт routing-профиля[/b]", classes="title")
            yield Label("Вставьте JSON профиля:")
            yield TextArea(id="ta-rp")
            with Horizontal(id="import-rp-buttons"):
                yield Button("Импортировать", variant="success", id="btn-rp-import")
                yield Button("Отмена", variant="error", id="btn-rp-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-rp-import":
            text = self.query_one("#ta-rp", TextArea).text
            self.dismiss({"text": text})
        else:
            self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)


class DashboardTab(Container):
    """Вкладка Dashboard."""

    status_text = reactive("Неизвестно")
    active_node_text = reactive("—")
    connection_time_text = reactive("—")
    traffic_rx_text = reactive("—")
    traffic_tx_text = reactive("—")
    routing_badge_text = reactive("—")

    def compose(self) -> ComposeResult:
        with Vertical(id="dashboard-vertical"):
            yield Static("[b]Subvost Xray TUN[/b]", id="dashboard-title", classes="title")
            with Grid(id="dashboard-grid"):
                with Vertical(classes="dashboard-card"):
                    yield Static("[b]Статус[/b]", classes="card-header")
                    yield Label(self.status_text, id="status-label")
                with Vertical(classes="dashboard-card"):
                    yield Static("[b]Активный узел[/b]", classes="card-header")
                    yield Label(self.active_node_text, id="active-node-label")
                with Vertical(classes="dashboard-card"):
                    yield Static("[b]Трафик[/b]", classes="card-header")
                    with Horizontal(id="traffic-row"):
                        yield Label(self.traffic_rx_text, id="traffic-rx-label")
                        yield Label(self.traffic_tx_text, id="traffic-tx-label")
                with Vertical(classes="dashboard-card"):
                    yield Static("[b]Время подключения[/b]", classes="card-header")
                    yield Label(self.connection_time_text, id="conn-time-label")
                with Vertical(classes="dashboard-card"):
                    yield Static("[b]Маршрутизация[/b]", classes="card-header")
                    yield Label(self.routing_badge_text, id="routing-badge-label")
            with Horizontal(id="dashboard-actions"):
                yield Button("▶ Старт", variant="success", id="btn-start")
                yield Button("■ Стоп", variant="error", id="btn-stop")
                yield Button("🔍 Диагностика", variant="primary", id="btn-diag")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-start":
            asyncio.create_task(app._action_start())
        elif btn_id == "btn-stop":
            asyncio.create_task(app._action_stop())
        elif btn_id == "btn-diag":
            asyncio.create_task(app._action_diag())

    def watch_status_text(self, value: str) -> None:
        try:
            label = self.query_one("#status-label", Label)
            label.update(value)
        except Exception:
            pass

    def watch_active_node_text(self, value: str) -> None:
        try:
            label = self.query_one("#active-node-label", Label)
            label.update(value)
        except Exception:
            pass

    def watch_traffic_rx_text(self, value: str) -> None:
        try:
            label = self.query_one("#traffic-rx-label", Label)
            label.update(value)
        except Exception:
            pass

    def watch_traffic_tx_text(self, value: str) -> None:
        try:
            label = self.query_one("#traffic-tx-label", Label)
            label.update(value)
        except Exception:
            pass

    def watch_routing_badge_text(self, value: str) -> None:
        try:
            label = self.query_one("#routing-badge-label", Label)
            label.update(value)
        except Exception:
            pass

    def watch_connection_time_text(self, value: str) -> None:
        try:
            label = self.query_one("#conn-time-label", Label)
            label.update(value)
        except Exception:
            pass


class NodesTab(Container):
    """Вкладка Узлы и подписки."""

    selected_row_key: str | None = None
    selected_sub_id: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="nodes-vertical"):
            yield Static("[b]Подписки[/b]", classes="section-header")
            with Horizontal(id="sub-actions"):
                yield Button("➕ Импорт подписки", id="btn-import-sub")
                yield Button("🔄 Обновить все", id="btn-refresh-all")
                yield Button("🔄 Обновить", id="btn-refresh-sub")
                yield Button("❌ Удалить", variant="error", id="btn-delete-sub")
            yield DataTable(id="sub-table")
            yield Static("[b]Узлы[/b]", classes="section-header")
            with Horizontal(id="nodes-actions"):
                yield Button("➕ Добавить вручную", id="btn-add-manual")
                yield Button("▶ Активировать", variant="success", id="btn-activate-node")
                yield Button("📡 Пинг", id="btn-ping-node")
            yield DataTable(id="nodes-table")
            yield Label("Выберите строку и нажмите действие", id="nodes-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-import-sub":
            app._action_import_subscription()
        elif btn_id == "btn-refresh-all":
            asyncio.create_task(app._action_refresh_all())
        elif btn_id == "btn-refresh-sub":
            asyncio.create_task(app._action_refresh_sub())
        elif btn_id == "btn-delete-sub":
            app._action_delete_sub()
        elif btn_id == "btn-add-manual":
            app._action_add_manual()
        elif btn_id == "btn-activate-node":
            asyncio.create_task(app._action_activate_node())
        elif btn_id == "btn-ping-node":
            asyncio.create_task(app._action_ping_node())

    def on_mount(self) -> None:
        sub_table = self.query_one("#sub-table", DataTable)
        sub_table.add_columns("Название", "URL", "Узлов", "Состояние")
        sub_table.cursor_type = "row"
        sub_table.zebra_stripes = True
        table = self.query_one("#nodes-table", DataTable)
        table.add_columns("Имя", "Протокол", "Сервер", "Пинг", "Подписка")
        table.cursor_type = "row"
        table.zebra_stripes = True
        # Заполняем данные при первом открытии
        app = self.app
        if isinstance(app, SubvostTUI):
            app._update_nodes()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id
        if table_id == "nodes-table":
            self.selected_row_key = str(event.row_key.value) if event.row_key else None
            hint = self.query_one("#nodes-hint", Label)
            if self.selected_row_key:
                hint.update(f"Выбран узел: {self.selected_row_key}")
        elif table_id == "sub-table":
            self.selected_sub_id = str(event.row_key.value) if event.row_key else None
            hint = self.query_one("#nodes-hint", Label)
            if self.selected_sub_id:
                hint.update(f"Выбрана подписка: {self.selected_sub_id}")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        table_id = event.data_table.id
        if table_id == "nodes-table":
            self.selected_row_key = str(event.row_key.value) if event.row_key else None
            hint = self.query_one("#nodes-hint", Label)
            if self.selected_row_key:
                hint.update(f"Выбран узел: {self.selected_row_key}")
        elif table_id == "sub-table":
            self.selected_sub_id = str(event.row_key.value) if event.row_key else None
            hint = self.query_one("#nodes-hint", Label)
            if self.selected_sub_id:
                hint.update(f"Выбрана подписка: {self.selected_sub_id}")


class LogTab(Container):
    """Вкладка Лог."""

    def compose(self) -> ComposeResult:
        with Vertical(id="log-vertical"):
            with Horizontal(id="log-actions"):
                yield Button("🔄 Обновить", id="btn-refresh-log")
                yield Select(
                    [("Все", "all"), ("Ошибки", "error"), ("Предупреждения", "warning"), ("Инфо", "info")],
                    value="all",
                    id="log-filter",
                )
            yield RichLog(id="log-viewer", highlight=True, wrap=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        if event.button.id == "btn-refresh-log":
            app._update_log()


class RoutingTab(Container):
    """Вкладка Маршрутизация."""

    selected_profile_id: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="routing-vertical"):
            # Секция 1: активный профиль (всегда видна)
            yield Static(id="routing-active-status")
            yield Static(id="routing-geodata-status")
            # Секция 2: кнопки действий
            with Horizontal(id="routing-actions"):
                yield Button("▶ Активировать", id="btn-activate-rp", variant="success", disabled=True)
                yield Button("⏸ Деактивировать", id="btn-deactivate-rp", variant="warning", disabled=True)
                yield Button("➕ Импорт", id="btn-import-rp", variant="default")
                yield Button("🔄 GeoIP/GeoSite", id="btn-refresh-geodata", variant="default")
            # Секция 3: двухколоночный layout
            with Horizontal(id="routing-columns"):
                with Vertical(id="routing-left"):
                    yield Static("[b]Профили маршрутизации[/b]", classes="section-header")
                    yield DataTable(id="routing-table", cursor_type="row")
                    yield Static("", id="routing-empty-hint")
                with Vertical(id="routing-right"):
                    yield Static("[b]Прямые маршруты[/b]", classes="section-header")
                    yield DataTable(id="routing-direct-table", cursor_type="cell")

    def on_mount(self) -> None:
        rt = self.query_one("#routing-table", DataTable)
        rt.add_columns("Имя", "Состояние", "Тип", "Правил")
        rt.cursor_type = "row"
        rt.zebra_stripes = True
        dt_direct = self.query_one("#routing-direct-table", DataTable)
        dt_direct.add_columns("Сеть", "Действие", "Источник")
        dt_direct.cursor_type = "cell"
        dt_direct.zebra_stripes = True
        app = self.app
        if isinstance(app, SubvostTUI):
            app._update_routing()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-activate-rp":
            asyncio.create_task(app._action_activate_profile())
        elif btn_id == "btn-deactivate-rp":
            asyncio.create_task(app._action_deactivate_profile())
        elif btn_id == "btn-import-rp":
            app._action_import_routing_profile()
        elif btn_id == "btn-refresh-geodata":
            asyncio.create_task(app._action_refresh_geodata())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_profile_id = str(event.row_key.value) if event.row_key else None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.selected_profile_id = str(event.row_key.value) if event.row_key else None


class SettingsTab(Container):
    """Вкладка Настройки."""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-vertical"):
            yield Static("[b]Настройки[/b]", classes="title")
            with Horizontal(classes="setting-row"):
                yield Label("Файловые логи:", classes="setting-label")
                yield Switch(id="sw-file-logs")
            with Horizontal(classes="setting-row"):
                yield Label("Retention (дней):", classes="setting-label")
                yield Input("7", id="inp-retention", classes="setting-input")
            with Horizontal(id="settings-actions"):
                yield Button("💾 Сохранить", variant="success", id="btn-save-settings")
                yield Button("🧹 Очистить артефакты", variant="warning", id="btn-cleanup")
            yield Static("[b]Ядро Xray[/b]", classes="section-header")
            with Horizontal(classes="setting-row"):
                yield Label("Текущая версия:", classes="setting-label")
                yield Static("...", id="lbl-xray-version")
            with Horizontal(classes="setting-row"):
                yield Label("Последняя версия:", classes="setting-label")
                yield Static("...", id="lbl-xray-latest")
            with Horizontal(id="xray-update-actions"):
                yield Button("🔍 Проверить обновления", id="btn-check-updates")
                yield Button("⬆ Обновить ядро Xray", variant="warning", id="btn-update-xray")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-save-settings":
            asyncio.create_task(app._action_save_settings())
        elif btn_id == "btn-cleanup":
            asyncio.create_task(app._action_cleanup())
        elif btn_id == "btn-check-updates":
            app._action_check_xray_updates()
        elif btn_id == "btn-update-xray":
            app._action_update_xray()


class SubvostTUI(App):
    """Главное TUI-приложение."""

    CSS = """
    Screen {
        align: center middle;
    }
    #dashboard-title {
        text-align: center;
        padding: 1 0;
    }
    .title {
        text-style: bold;
        color: $text-accent;
    }
    .dashboard-card {
        border: solid $primary;
        padding: 1 2;
        height: auto;
    }
    .card-header {
        text-style: bold;
        color: $text-accent;
        margin-bottom: 1;
    }
    #dashboard-grid {
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
    }
    #dashboard-actions {
        height: auto;
        margin-top: 1;
    }
    #dashboard-actions Button {
        margin: 0 1;
    }
    #traffic-row {
        height: auto;
    }
    #traffic-row Label {
        margin-right: 2;
    }
    #nodes-actions, #log-actions, #routing-actions, #settings-actions, #xray-update-actions {
        height: auto;
        margin-bottom: 1;
    }
    #nodes-actions Button, #log-actions Button, #routing-actions Button, #settings-actions Button, #xray-update-actions Button {
        margin: 0 1;
    }
    #main-container {
        height: 1fr;
    }
    #main-tabs {
        height: 1fr;
    }
    #footer-bar {
        height: auto;
        width: 100%;
        align: center middle;
        background: $surface-darken-1;
        padding: 0 1;
    }
    #footer-bar Button {
        margin: 0 2;
    }
    #import-sub-container, #import-link-container {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #import-sub-buttons, #import-link-buttons, #import-rp-buttons {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    #import-sub-buttons Button, #import-link-buttons Button, #import-rp-buttons Button {
        margin: 0 1;
    }
    #import-rp-container {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #log-viewer {
        height: 1fr;
        border: solid $primary;
    }
    .setting-row {
        height: auto;
        margin: 1 0;
    }
    .setting-label {
        width: 24;
        content-align-vertical: middle;
    }
    .setting-input {
        width: 12;
    }
    #loading-container {
        width: 40;
        height: 5;
        border: solid $accent;
        background: $surface;
        content-align: center middle;
    }
    #confirm-container {
        width: 50;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #confirm-message {
        margin-bottom: 1;
    }
    #confirm-buttons {
        height: auto;
        align: center middle;
    }
    #confirm-buttons Button {
        margin: 0 1;
    }
    #lock-conflict-container {
        width: 55;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #lock-conflict-buttons {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    #lock-conflict-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("alt+q", "quit", "Выход"),
        ("alt+r", "refresh", "Обновить"),
        ("alt+p", "command_palette", "Команды"),
        ("alt+й", "quit", ""),
        ("alt+к", "refresh", ""),
        ("alt+з", "command_palette", ""),
    ]

    def __init__(self, service: SubvostAppService | None = None) -> None:
        self.service = service
        self._status: dict[str, Any] = {}
        self._store: dict[str, Any] = {}
        self.runtime_adapter = ShellRuntimeAdapter(
            project_root=PROJECT_ROOT,
            libexec_dir=PROJECT_ROOT / "libexec",
        )
        self.network_adapter = SystemNetworkAdapter()
        self._action_in_progress: bool = False
        super().__init__()

    def _check_lock_conflict(self) -> tuple[int, str] | None:
        """Проверяет per-bundle lock на конфликт.

        Возвращает None если конфликта нет (lock захвачен).
        Возвращает (pid, project_root) если другой TUI из этого же bundle уже запущен.
        """
        if not TUI_LOCK_PATH.exists():
            return None

        try:
            content = TUI_LOCK_PATH.read_text().strip()
            lines = content.split("\n")
            if len(lines) < 1:
                raise ValueError("повреждённый lock-файл")
            lock_pid = int(lines[0].strip())
            lock_root = lines[1].strip() if len(lines) >= 2 else "неизвестно"
        except Exception:
            # Повреждённый lock → перезаписываем
            return None

        # Проверяем, жив ли процесс
        try:
            os.kill(lock_pid, 0)
        except ProcessLookupError:
            # PID мёртв → stale lock, очистим
            return None
        except PermissionError:
            pass  # Чужой процесс — считаем живым

        # Процесс жив — конфликт
        return (lock_pid, lock_root)

    async def _kill_old_instance(self, pid: int) -> None:
        """Мягко убивает старый TUI процесс: SIGTERM, ждёт 2 сек, SIGKILL."""
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return

        for _ in range(4):
            await asyncio.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return  # Процесс завершился

        # Принудительно
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="main-container"):
            with TabbedContent(id="main-tabs"):
                with TabPane("Подключение", id="tab-dashboard"):
                    yield DashboardTab(id="dashboard-tab")
                with TabPane("Подписки", id="tab-nodes"):
                    yield NodesTab(id="nodes-tab")
                with TabPane("Лог", id="tab-log"):
                    yield LogTab(id="log-tab")
                with TabPane("Маршруты", id="tab-routing"):
                    yield RoutingTab(id="routing-tab")
                with TabPane("Настройки", id="tab-settings"):
                    yield SettingsTab(id="settings-tab")
            with Horizontal(id="footer-bar"):
                yield Button("Обновить  Alt+R", id="btn-footer-refresh")
                yield Button("Команды   Alt+P", id="btn-footer-palette")
                yield Button("Выход     Alt+Q", id="btn-footer-quit")

    async def on_mount(self) -> None:
        # 1. Lock check — самый первый шаг
        force = "--force" in sys.argv
        conflict = self._check_lock_conflict()
        if conflict:
            lock_pid, lock_root = conflict
            if force:
                await self._kill_old_instance(lock_pid)
            else:
                future: asyncio.Future[bool] = asyncio.Future()
                self.push_screen(
                    TuiLockConflictModal(lock_pid, lock_root),
                    callback=lambda result: future.set_result(result),
                )
                proceed = await future
                if not proceed:
                    self.exit()
                    return
                await self._kill_old_instance(lock_pid)

        # Блокировка захвачена — пишем lock
        _write_tui_lock()

        # 2. Инициализация сервиса
        if self.service is None:
            try:
                self.service = build_default_service(SCRIPT_DIR)
            except Exception as exc:
                self.notify(f"Ошибка инициализации сервиса: {exc}", severity="error")
                return

        # 3. Стартовая логика (без изменений)
        self.set_interval(2.0, self._update_dashboard)
        self._update_dashboard()
        self._update_nodes()
        self._update_settings()
        self._start_tray()
        await self._auto_activate_first_node()
        asyncio.create_task(self._refresh_xray_version_label())

    def _update_dashboard(self) -> None:
        if self.service is None:
            return
        try:
            status = self.service.collect_status()
            self._status = status
        except Exception as exc:
            self.notify(f"Ошибка получения статуса: {exc}", severity="error")
            return

        vm = build_view_model(status)
        dashboard = self.query_one("#dashboard-tab", DashboardTab)
        dashboard.status_text = vm.connection_label
        dashboard.active_node_text = vm.active_node_name or "—"
        dashboard.traffic_rx_text = vm.traffic_rx_text
        dashboard.traffic_tx_text = vm.traffic_tx_text
        dashboard.routing_badge_text = vm.routing_active_profile_name or "Нет профиля"

        connected_since = status.get("runtime", {}).get("connected_since")
        if connected_since:
            try:
                start = datetime.datetime.fromisoformat(connected_since)
                now = datetime.datetime.now(start.tzinfo) if start.tzinfo else datetime.datetime.now()
                elapsed = now - start
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                dashboard.connection_time_text = f"Время: {hours:02d}:{minutes:02d}:{seconds:02d}"
            except Exception:
                dashboard.connection_time_text = "—"
        else:
            dashboard.connection_time_text = "—"

    def _update_nodes(self) -> None:
        if self.service is None:
            return
        try:
            snapshot = self.service.collect_store_snapshot()
            # collect_store_snapshot возвращает {"store": store_payload(), ...}
            # store_payload() содержит {"store": real_store, ...}
            store_payload = snapshot.get("store", {})
            store = store_payload.get("store", {})
            self._store = store
        except Exception as exc:
            self.notify(f"Ошибка загрузки store: {exc}", severity="error")
            return

        try:
            sub_table = self.query_one("#sub-table", DataTable)
            sub_table.clear()
            for sub in store.get("subscriptions", []):
                profile = next((p for p in store.get("profiles", []) if p.get("id") == sub.get("profile_id")), {})
                node_count = len(profile.get("nodes", []))
                enabled = "Вкл" if sub.get("enabled", True) else "Выкл"
                sub_table.add_row(
                    sub.get("name", "—"),
                    sub.get("url", "—")[:40] + "..." if len(sub.get("url", "")) > 40 else sub.get("url", "—"),
                    str(node_count),
                    enabled,
                    key=sub.get("id", ""),
                )

            table = self.query_one("#nodes-table", DataTable)
            table.clear()
            for profile in store.get("profiles", []):
                profile_name = profile.get("name", "Без имени")
                for node in profile.get("nodes", []):
                    vm = build_view_model(self._status)
                    ping_key = f"{profile.get('id')}:{node.get('id')}"
                    ping_val = vm.ping_for_node(profile.get('id'), node.get('id'))
                    row = (
                        node.get("name", "—"),
                        node.get("protocol", "—"),
                        node.get("server", "—"),
                        str(ping_val),
                        profile_name,
                    )
                    table.add_row(*row, key=ping_key)
        except Exception:
            # Вкладка еще не смонтирована — игнорируем
            pass

    def _update_log(self) -> None:
        log_tab = self.query_one("#log-tab", LogTab)
        viewer = log_tab.query_one("#log-viewer", RichLog)
        viewer.clear()

        filter_widget = log_tab.query_one("#log-filter", Select)
        level_filter = str(filter_widget.value or "all")

        if self.service is None:
            return

        logs = self.service.collect_log_payload()
        entries = logs.get("entries", [])
        for entry in entries:
            lvl = entry.get("level", "info")
            if level_filter != "all" and lvl != level_filter:
                continue
            ts = entry.get("timestamp", "")
            src = entry.get("source", "")
            name = entry.get("name", "")
            msg = entry.get("message", "")
            line = f"[{ts}] [{src}/{name}] {msg}"
            color = "white"
            if lvl == "error":
                color = "red"
            elif lvl == "warning":
                color = "yellow"
            viewer.write(f"[{color}]{line}[/{color}]")

    def _update_routing(self) -> None:
        if self.service is None:
            return
        try:
            snapshot = self.service.collect_store_snapshot()
            store_payload = snapshot.get("store", {})
            store = store_payload.get("store", {})
            if not store:
                return
            self._store = store
        except Exception as exc:
            self.notify(f"Ошибка обновления store: {exc}", severity="error")
            return

        try:
            repo = JsonRoutingRepository(self._store)
            profiles = repo.get_all()
            active = repo.get_active()
            routing_state = self._store.get("routing", {})
            runtime_ready = bool(routing_state.get("runtime_ready", False))
            runtime_error = str(routing_state.get("runtime_error") or "")
            geodata = routing_state.get("geodata", {})
            geodata_ready = bool(geodata.get("ready", False))
            routing_tab = self.query_one("#routing-tab", RoutingTab)

            # Секция 1: верхний статус
            active_name = active.name if active else "—"
            if active:
                active_status = f"[bold green]★ Активный профиль: {active_name}[/bold green]"
            else:
                active_status = "[dim]✕ Активный профиль не выбран[/dim]"
            self.query_one("#routing-active-status", Static).update(active_status)

            if geodata_ready:
                geodata_status = "[green]GeoIP/GeoSite: готовы[/green]"
            elif runtime_error:
                geodata_status = f"[red]GeoIP/GeoSite: ошибка — {runtime_error}[/red]"
            else:
                geodata_status = "[yellow]GeoIP/GeoSite: не подготовлены[/yellow]"
            self.query_one("#routing-geodata-status", Static).update(geodata_status)

            # Чувствительность кнопок
            activate_btn = self.query_one("#btn-activate-rp", Button)
            deactivate_btn = self.query_one("#btn-deactivate-rp", Button)
            selected_profile_id = routing_tab.selected_profile_id
            activate_btn.disabled = not selected_profile_id or (active is not None and str(selected_profile_id) == str(active.id))
            deactivate_btn.disabled = active is None

            # Таблица профилей
            rt = self.query_one("#routing-table", DataTable)
            rt.clear()
            for rp in profiles:
                is_active = active is not None and active.id == rp.id
                name_display = f"★ {rp.name}" if is_active else rp.name
                status_display = "★ Активен" if is_active else "—"
                type_display = "Авто" if rp.auto_managed else "Вручную"
                rt.add_row(
                    name_display,
                    status_display,
                    type_display,
                    str(rp.total_rules),
                    key=rp.id,
                )

            # Подсказка если нет профилей
            empty_hint = self.query_one("#routing-empty-hint", Static)
            if not profiles:
                empty_hint.update("[dim]Нет профилей маршрутизации. Нажмите «+ Импорт» чтобы добавить.[/dim]")
            else:
                empty_hint.update("")

            # Прямые маршруты (человекочитаемые)
            dt = self.query_one("#routing-direct-table", DataTable)
            dt.clear()
            action_map = {
                "direct": "напрямую",
                "proxy": "через прокси",
                "block": "блокировать",
            }
            source_map = {
                "Template": "встроенное",
                "Routing-профиль": "из профиля",
            }

            def _humanize_network(raw: str) -> str:
                if raw.startswith("geoip:"):
                    return f"GeoIP: {raw[6:]}"
                if raw.startswith("geosite:"):
                    return f"GeoSite: {raw[8:]}"
                return raw

            def _humanize_action(raw: str) -> str:
                return action_map.get(raw, raw)

            def _humanize_source(raw: str) -> str:
                return source_map.get(raw, raw)

            vm = build_view_model(self._status)
            for item in vm.direct_report_entries:
                dt.add_row(
                    _humanize_network(item.get("network", "—")),
                    _humanize_action(item.get("action", "—")),
                    _humanize_source(item.get("source", "—")),
                )
        except Exception:
            self.log.exception("Ошибка обновления routing-таба")

    def _update_settings(self) -> None:
        if self.service is None:
            return
        try:
            settings = self.service.load_settings()
        except Exception:
            return
        tab = self.query_one("#settings-tab", SettingsTab)
        sw = tab.query_one("#sw-file-logs", Switch)
        sw.value = bool(settings.get("file_logs_enabled", False))
        inp = tab.query_one("#inp-retention", Input)
        inp.value = str(settings.get("artifact_retention_days", 7))


    async def _show_loading(self, message: str = "Выполнение...") -> LoadingModal:
        modal = LoadingModal(message)
        await self.push_screen(modal)
        return modal

    def _hide_loading(self, modal: LoadingModal | None) -> None:
        if modal is not None and self.is_screen_installed(modal):
            try:
                self.pop_screen()
            except Exception:
                pass

    async def _run_service_action(self, action_name: str, func, *args, **kwargs) -> Any:
        modal = await self._show_loading(action_name)
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            return result
        except Exception as exc:
            self.notify(str(exc), severity="error")
            raise
        finally:
            self._hide_loading(modal)

    async def _auto_activate_first_node(self) -> None:
        if self.service is None:
            return
        store = self.service.ensure_store_ready()
        selection = store.get("active_selection", {})
        if selection.get("profile_id") and selection.get("node_id"):
            return

        first_profile = None
        first_node = None
        for profile in store.get("profiles", []):
            if not profile.get("enabled", True):
                continue
            for node in profile.get("nodes", []):
                if node.get("enabled", True):
                    first_profile = profile
                    first_node = node
                    break
            if first_node:
                break

        if first_node is None:
            return

        try:
            repo = JsonNodeRepository(store)
            repo.activate(first_profile["id"], first_node["id"])
            self.service.persist_store(store)
            self.notify(
                f"Автоматически активирован узел: {first_node.get('name', '—')}",
                severity="information",
            )
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._update_dashboard()
            self._update_nodes()



    async def _action_start(self) -> None:
        if self.service is None:
            return
        if self._action_in_progress:
            self.notify("Действие уже выполняется, подождите...", severity="warning")
            return
        self._action_in_progress = True
        try:
            await self._run_service_action("Запуск подключения...", self.runtime_adapter.start_runtime, self.service)
            self.notify("Подключение запущено", severity="information")
            self._update_dashboard()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._action_in_progress = False
            self._update_dashboard()

    async def _action_stop(self) -> None:
        if self.service is None:
            return
        if self._action_in_progress:
            self.notify("Действие уже выполняется, подождите...", severity="warning")
            return
        self._action_in_progress = True
        try:
            await self._run_service_action("Остановка подключения...", self.runtime_adapter.stop_runtime, self.service)
            self.notify("Подключение остановлено", severity="information")
            self._update_dashboard()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._action_in_progress = False
            self._update_dashboard()

    async def _action_diag(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action("Снятие диагностики...", self.runtime_adapter.diagnose, self.service)
            self.notify("Диагностика сохранена", severity="information")
            self._update_dashboard()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._update_dashboard()

    async def _do_import_subscription(self, result: dict[str, str] | None) -> None:
        if result is None or self.service is None:
            return
        try:
            def _do_add():
                store = self.service.ensure_store_ready()
                repo = JsonSubscriptionRepository(store)
                sub = repo.add_subscription(result["name"], result["url"])
                self.service.persist_store(store)
                return sub
            await self._run_service_action("Добавление подписки...", _do_add)
            self.notify("Подписка добавлена", severity="information")
            self._update_nodes()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка: {exc}", severity="error")

    def _action_import_subscription(self) -> None:
        if self.service is None:
            return
        self.push_screen(ImportSubscriptionModal(), callback=lambda r: asyncio.create_task(self._do_import_subscription(r)))

    async def _action_refresh_all(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action("Обновление подписок...", self.service.refresh_all_subscriptions)
            self.notify("Подписки обновлены", severity="information")
            self._update_nodes()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._update_nodes()

    async def _do_add_manual(self, result: dict[str, Any] | None) -> None:
        if result is None or self.service is None:
            return
        try:
            def _do_import():
                store = self.service.ensure_store_ready()
                results = preview_links(result["text"])
                valid = sum(1 for r in results if r.get("valid"))
                if valid == 0:
                    raise ValueError("Нет валидных ссылок.")
                save_result = save_manual_import_results(
                    store, results, activate_single=result["activate_single"]
                )
                self.service.persist_store(store)
                return save_result
            save_result = await self._run_service_action("Импорт ссылок...", _do_import)
            self.notify(f"Импортировано узлов: {len(save_result.get('added', []))}", severity="information")
            self._update_nodes()
            self._update_dashboard()
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def _action_add_manual(self) -> None:
        if self.service is None:
            return
        self.push_screen(ImportLinkModal(), callback=lambda r: asyncio.create_task(self._do_add_manual(r)))

    async def _action_activate_node(self) -> None:
        if self.service is None:
            return
        nodes_tab = self.query_one("#nodes-tab", NodesTab)
        key = nodes_tab.selected_row_key
        if not key:
            self.notify("Сначала выберите строку в таблице узлов", severity="warning")
            return
        parts = key.split(":", 1)
        if len(parts) != 2:
            return
        profile_id, node_id = parts
        try:
            def _do_activate():
                store = self.service.ensure_store_ready()
                repo = JsonNodeRepository(store)
                repo.activate(profile_id, node_id)
                self.service.persist_store(store)
                return {"ok": True}
            await self._run_service_action("Активация узла...", _do_activate)
            self.notify("Узел активирован", severity="information")
            self._update_dashboard()
            self._update_nodes()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._update_dashboard()
            self._update_nodes()

    async def _action_ping_node(self) -> None:
        if self.service is None:
            return
        nodes_tab = self.query_one("#nodes-tab", NodesTab)
        key = nodes_tab.selected_row_key
        if not key:
            self.notify("Сначала выберите строку в таблице узлов", severity="warning")
            return
        parts = key.split(":", 1)
        if len(parts) != 2:
            return
        profile_id, node_id = parts
        try:
            result = await self._run_service_action(
                "Пинг узла...",
                self.network_adapter.ping_via_service,
                self.service,
                profile_id,
                node_id,
            )
            latency = result.get("latency_ms", "—")
            self.notify(f"Пинг: {latency} мс", severity="information")
            self._update_nodes()
        except Exception as exc:
            self.notify(f"Ошибка пинга: {exc}", severity="error")

    async def _action_refresh_sub(self) -> None:
        if self.service is None:
            return
        nodes_tab = self.query_one("#nodes-tab", NodesTab)
        sub_id = nodes_tab.selected_sub_id
        if not sub_id:
            self.notify("Сначала выберите подписку в таблице", severity="warning")
            return
        try:
            await self._run_service_action(
                "Обновление подписки...",
                self.service.refresh_subscription,
                sub_id,
            )
            self.notify("Подписка обновлена", severity="information")
            self._update_nodes()
        except Exception as exc:
            self.notify(f"Ошибка обновления: {exc}", severity="error")

    async def _do_delete_sub(self, confirmed: bool) -> None:
        if not confirmed or self.service is None:
            return
        nodes_tab = self.query_one("#nodes-tab", NodesTab)
        sub_id = nodes_tab.selected_sub_id
        if not sub_id:
            self.notify("Сначала выберите подписку в таблице", severity="warning")
            return
        try:
            await self._run_service_action(
                "Удаление подписки...",
                self.service.delete_subscription,
                sub_id,
            )
            self.notify("Подписка удалена", severity="information")
            self._update_nodes()
        except Exception as exc:
            self.notify(f"Ошибка удаления: {exc}", severity="error")

    def _action_delete_sub(self) -> None:
        if self.service is None:
            return
        nodes_tab = self.query_one("#nodes-tab", NodesTab)
        sub_id = nodes_tab.selected_sub_id
        if not sub_id:
            self.notify("Сначала выберите подписку в таблице", severity="warning")
            return
        self.push_screen(ConfirmModal("Удалить выбранную подписку?"), callback=lambda c: asyncio.create_task(self._do_delete_sub(c)))

    async def _action_refresh_geodata(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action(
                "Обновление geodata...",
                self.service.prepare_routing_geodata,
            )
            self.notify("GeoIP/GeoSite обновлены", severity="information")
            self._update_routing()
        except Exception as exc:
            self.notify(f"Ошибка обновления geodata: {exc}", severity="error")


    async def _action_activate_profile(self) -> None:
        if self.service is None:
            return
        routing_tab = self.query_one("#routing-tab", RoutingTab)
        if not routing_tab.selected_profile_id:
            self.notify("Выберите профиль в таблице.", severity="warning")
            return
        try:
            await self._run_service_action(
                "Активация профиля маршрутизации...",
                self.service.activate_routing_profile,
                routing_tab.selected_profile_id,
            )
            self._update_routing()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка активации: {exc}", severity="error")

    async def _action_deactivate_profile(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action(
                "Деактивация профиля маршрутизации...",
                self.service.clear_active_routing_profile,
            )
            self._update_routing()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка деактивации: {exc}", severity="error")

    async def _do_import_routing_profile(self, result: dict[str, str] | None) -> None:
        if result is None or self.service is None:
            return
        try:
            await self._run_service_action(
                "Импорт профиля...",
                self.service.import_routing_profile,
                result["text"],
            )
            self.notify("Профиль импортирован", severity="information")
            self._update_routing()
        except Exception as exc:
            self.notify(f"Ошибка импорта: {exc}", severity="error")

    def _action_import_routing_profile(self) -> None:
        if self.service is None:
            return
        self.push_screen(ImportRoutingProfileModal(), callback=lambda r: asyncio.create_task(self._do_import_routing_profile(r)))

    async def _action_save_settings(self) -> None:
        if self.service is None:
            return
        tab = self.query_one("#settings-tab", SettingsTab)
        sw = tab.query_one("#sw-file-logs", Switch)
        inp = tab.query_one("#inp-retention", Input)
        try:
            retention = int(inp.value or 7)
        except ValueError:
            retention = 7
        try:
            self.service.save_settings(
                file_logs_enabled=sw.value,
                artifact_retention_days=retention,
            )
            self.notify("Настройки сохранены", severity="information")
        except Exception as exc:
            self.notify(f"Ошибка сохранения: {exc}", severity="error")

    async def _action_cleanup(self) -> None:
        if self.service is None:
            return
        def do_cleanup():
            return self.service.cleanup_runtime_artifacts()
        try:
            result = await self._run_service_action("Очистка артефактов...", do_cleanup)
            removed = result.get("removed", [])
            self.notify(f"Очищено файлов: {len(removed)}", severity="information")
            self._update_dashboard()
        except Exception as exc:
            self.notify(str(exc), severity="error")
        finally:
            self._update_dashboard()

    def _action_check_xray_updates(self) -> None:
        """Проверить последнюю доступную версию xray через GitHub API."""
        if self.service is None:
            return
        async def _run():
            def do_check():
                return self.service.get_latest_xray_version()
            try:
                latest = await self._run_service_action("Проверка обновлений Xray...", do_check)
                tab = self.query_one("#settings-tab", SettingsTab)
                lbl = tab.query_one("#lbl-xray-latest", Static)
                lbl.update(latest or "ошибка запроса")
                if latest:
                    current = await asyncio.to_thread(self.service.get_xray_version)
                    if current and current != latest:
                        self.notify(f"Доступна новая версия Xray: {latest}", severity="warning")
                    else:
                        self.notify("У вас последняя версия Xray", severity="information")
            except Exception as exc:
                self.notify(f"Ошибка проверки: {exc}", severity="error")
        asyncio.create_task(_run())

    def _action_update_xray(self) -> None:
        """Запустить обновление ядра Xray (с подтверждением)."""
        if self.service is None:
            return
        self.push_screen(
            ConfirmModal("Обновить ядро Xray? Потребуется пароль (pkexec) и интернет."),
            callback=lambda c: asyncio.create_task(self._do_update_xray(c)),
        )

    async def _do_update_xray(self, confirmed: bool) -> None:
        if not confirmed or self.service is None:
            return
        def do_update():
            return self.service.update_xray_core()
        try:
            result = await self._run_service_action("Обновление ядра Xray...", do_update)
            last_action = result.get("last_action", {})
            if last_action.get("ok"):
                self.notify("Ядро Xray обновлено", severity="information")
            else:
                self.notify(f"Ошибка обновления: {last_action.get('message', '?')}", severity="error")
            self._update_settings()
            asyncio.create_task(self._refresh_xray_version_label())
        except ValueError as exc:
            self.notify(str(exc), severity="error")
        except Exception as exc:
            self.notify(f"Ошибка: {exc}", severity="error")


    async def _refresh_xray_version_label(self) -> None:
        """Асинхронно обновляет метку текущей версии xray в настройках."""
        if self.service is None:
            return
        try:
            version = await asyncio.to_thread(self.service.get_xray_version)
            tab = self.query_one("#settings-tab", SettingsTab)
            lbl = tab.query_one("#lbl-xray-version", Static)
            lbl.update(version or "не найден")
        except Exception:
            pass

    def _stop_tray(self) -> None:
        """Остановить tray-процесс, если запущен."""
        tray_script = "tui_tray.py"
        try:
            result = subprocess.run(
                ["pgrep", "-f", tray_script],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().splitlines():
                try:
                    pid = int(line.strip())
                    if pid != os.getpid():
                        os.kill(pid, signal.SIGTERM)
                except (ValueError, OSError):
                    continue
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    def _start_tray(self) -> None:
        """Запустить tray-процесс в фоне."""
        tray_path = SCRIPT_DIR / "tui_tray.py"
        if tray_path.exists():
            subprocess.Popen(
                [sys.executable, str(tray_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-footer-refresh":
            self.action_refresh()
        elif btn_id == "btn-footer-palette":
            self.action_command_palette()
        elif btn_id == "btn-footer-quit":
            self.action_quit()

    def action_refresh(self) -> None:
        active_tab = self.query_one(TabbedContent).active
        if active_tab == "tab-dashboard":
            self._update_dashboard()
        elif active_tab == "tab-nodes":
            self._update_nodes()
        elif active_tab == "tab-log":
            self._update_log()
        elif active_tab == "tab-routing":
            self._update_routing()
        elif active_tab == "tab-settings":
            self._update_settings()

    def on_tabbed_content_tab_activated(self, event) -> None:
        tab_id = event.tab.id
        if tab_id == "tab-log":
            self._update_log()
        elif tab_id == "tab-nodes":
            self._update_nodes()
        elif tab_id == "tab-routing":
            self._update_routing()
        elif tab_id == "tab-settings":
            self._update_settings()


    def _do_quit(self, confirmed: bool) -> None:
        if confirmed:
            self._stop_tray()
            self.exit()

    def action_quit(self) -> None:
        if self.service is None:
            self._stop_tray()
            self.exit()
            return
        try:
            status = self.service.collect_status()
            runtime_live = status.get("processes", {}).get("xray_alive", False)
            if runtime_live:
                self.push_screen(ConfirmModal("VPN-подключение активно. Остановить и выйти?"), callback=self._do_quit)
            else:
                self._stop_tray()
                self.exit()
        except Exception:
            self._stop_tray()
            self.exit()


def main() -> None:
    # Миграция: удалить старый общий lock из ~/.config
    _migrate_old_lock()
    atexit.register(_cleanup_tui_lock)
    app = SubvostTUI()
    app.run()


if __name__ == "__main__":
    main()