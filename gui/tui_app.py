#!/usr/bin/env python3
"""Универсальный TUI-фронт Subvost Xray TUN на textual."""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult, NoMatches
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

from subvost_app_service import (
    SubvostAppService,
    build_default_service,
    humanize_bytes,
)
from subvost_parser import preview_links
from subvost_store import save_manual_import_results, store_payload

TUI_APP_ID = "io.subvost.XrayTun.TUI"
TUI_TITLE = "Subvost Xray TUN"


def _run_in_thread(func, *args, **kwargs):
    """Запускает функцию в потоке и возвращает результат через future."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(func, *args, **kwargs).result()


class LoadingModal(ModalScreen):
    """Модальный экран загрузки с сообщением."""

    def __init__(self, message: str = "Выполнение...") -> None:
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="loading-container"):
            yield Label(self.message, id="loading-label")


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
                    yield Label(self.traffic_rx_text, id="traffic-rx-label")
                    yield Label(self.traffic_tx_text, id="traffic-tx-label")
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
            self.selected_row_key = str(event.row_key) if event.row_key else None
            hint = self.query_one("#nodes-hint", Label)
            if self.selected_row_key:
                hint.update(f"Выбран узел: {self.selected_row_key}")
        elif table_id == "sub-table":
            self.selected_sub_id = str(event.row_key) if event.row_key else None
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
            with Horizontal(id="routing-actions"):
                yield Button("🔄 Обновить geodata", id="btn-refresh-geodata")
                yield Button("➕ Импорт профиля", id="btn-import-rp")
                yield Button("▶ Активировать профиль", variant="success", id="btn-activate-rp")
                yield Button("Вкл/Выкл маршрутизацию", id="btn-toggle-routing")
                yield Button("❌ Сбросить профиль", variant="error", id="btn-clear-rp")
            yield Static("[b]Routing-профили[/b]", classes="section-header")
            yield DataTable(id="routing-table")
            yield Label("Выберите профиль и нажмите действие", id="routing-hint")
            yield Static("[b]Прямые маршруты[/b]", classes="section-header")
            yield DataTable(id="direct-table")

    def on_mount(self) -> None:
        rt = self.query_one("#routing-table", DataTable)
        rt.add_columns("Имя", "Состояние", "Тип")
        rt.cursor_type = "row"
        rt.zebra_stripes = True
        dt = self.query_one("#direct-table", DataTable)
        dt.add_columns("Сеть", "Действие", "Источник")
        dt.cursor_type = "row"
        dt.zebra_stripes = True
        # Заполняем данные при первом открытии
        app = self.app
        if isinstance(app, SubvostTUI):
            app._update_routing()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-refresh-geodata":
            asyncio.create_task(app._action_refresh_geodata())
        elif btn_id == "btn-import-rp":
            app._action_import_routing_profile()
        elif btn_id == "btn-activate-rp":
            asyncio.create_task(app._action_activate_routing_profile())
        elif btn_id == "btn-toggle-routing":
            asyncio.create_task(app._action_toggle_routing())
        elif btn_id == "btn-clear-rp":
            app._action_clear_routing_profile()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected_profile_id = str(event.row_key) if event.row_key else None
        hint = self.query_one("#routing-hint", Label)
        if self.selected_profile_id:
            hint.update(f"Выбран профиль: {self.selected_profile_id}")


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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        app = self.app
        if not isinstance(app, SubvostTUI):
            return
        btn_id = event.button.id
        if btn_id == "btn-save-settings":
            asyncio.create_task(app._action_save_settings())
        elif btn_id == "btn-cleanup":
            asyncio.create_task(app._action_cleanup())


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
    #nodes-actions, #log-actions, #routing-actions, #settings-actions {
        height: auto;
        margin-bottom: 1;
    }
    #nodes-actions Button, #log-actions Button, #routing-actions Button, #settings-actions Button {
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
    """

    BINDINGS = [
        ("alt+q", "quit", "Выход"),
        ("alt+r", "refresh", "Обновить"),
        ("alt+p", "command_palette", "Команды"),
    ]

    def __init__(self, service: SubvostAppService | None = None) -> None:
        self.service = service
        self._status: dict[str, Any] = {}
        self._store: dict[str, Any] = {}
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
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

    def on_mount(self) -> None:
        if self.service is None:
            try:
                self.service = build_default_service(SCRIPT_DIR)
            except Exception as exc:
                self.notify(f"Ошибка инициализации сервиса: {exc}", severity="error")
                return
        self.set_interval(2.0, self._update_dashboard)
        self._update_dashboard()
        self._update_nodes()
        self._update_settings()

    def _update_dashboard(self) -> None:
        if self.service is None:
            return
        try:
            status = self.service.collect_status()
            self._status = status
        except Exception as exc:
            self.notify(f"Ошибка получения статуса: {exc}", severity="error")
            return

        dashboard = self.query_one("#dashboard-tab", DashboardTab)
        summary = status.get("summary", {})
        state_label = summary.get("label", "—")
        dashboard.status_text = state_label

        active_node = status.get("active_node")
        if active_node:
            dashboard.active_node_text = active_node.get("name", "—")
        else:
            dashboard.active_node_text = "—"

        traffic = status.get("traffic", {})
        rx = traffic.get("rx_bytes")
        tx = traffic.get("tx_bytes")
        dashboard.traffic_rx_text = f"↓ {humanize_bytes(rx)}"
        dashboard.traffic_tx_text = f"↑ {humanize_bytes(tx)}"

        routing = status.get("routing", {})
        active_rp = routing.get("active_profile")
        if active_rp:
            dashboard.routing_badge_text = active_rp.get("name", "—")
        else:
            dashboard.routing_badge_text = "Нет профиля"

        processes = status.get("processes", {})
        is_live = bool(processes.get("xray_alive"))
        try:
            start_btn = dashboard.query_one("#btn-start", Button)
            stop_btn = dashboard.query_one("#btn-stop", Button)
            start_btn.disabled = is_live
            stop_btn.disabled = not is_live
        except NoMatches:
            pass

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
                    (sub.get("url") or "—")[:40] + "..." if len(sub.get("url") or "") > 40 else (sub.get("url") or "—"),
                    str(node_count),
                    enabled,
                    key=sub.get("id") or "",
                )

            table = self.query_one("#nodes-table", DataTable)
            table.clear()
            for profile in store.get("profiles", []):
                profile_name = profile.get("name", "Без имени")
                for node in profile.get("nodes", []):
                    ping_cache = self._status.get("ping", {}).get("cache", {})
                    ping_key = f"{profile.get('id')}:{node.get('id')}"
                    ping_val = ping_cache.get(ping_key, "—")
                    row = (
                        node.get("name", "—"),
                        node.get("protocol", "—"),
                        node.get("server", "—"),
                        str(ping_val),
                        profile_name,
                    )
                    table.add_row(*row, key=ping_key)
        except NoMatches:
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
        if not self._store:
            return
        try:
            rt = self.query_one("#routing-table", DataTable)
            rt.clear()
            for rp in self._store.get("routing_profiles", []):
                enabled = "Вкл" if rp.get("enabled") else "Выкл"
                rt.add_row(
                    rp.get("name", "—"),
                    enabled,
                    rp.get("type", "custom"),
                    key=rp.get("id") or "",
                )

            dt = self.query_one("#direct-table", DataTable)
            dt.clear()
            direct_report = self._status.get("direct_report", {})
            for item in direct_report.get("entries", []):
                dt.add_row(
                    item.get("network", "—"),
                    item.get("action", "—"),
                    item.get("source", "—"),
                )
        except NoMatches:
            # Вкладка еще не смонтирована — игнорируем
            pass

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

    def _show_loading(self, message: str = "Выполнение...") -> None:
        self.push_screen(LoadingModal(message))

    def _hide_loading(self) -> None:
        self.pop_screen()

    async def _run_service_action(self, action_name: str, func, *args, **kwargs) -> Any:
        self._show_loading(action_name)
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            return result
        except Exception as exc:
            self.notify(str(exc), severity="error")
            raise
        finally:
            self._hide_loading()



    async def _action_start(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action("Запуск подключения...", self.service.start_runtime)
            self.notify("Подключение запущено", severity="information")
            self._update_dashboard()
        except Exception:
            pass

    async def _action_stop(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action("Остановка подключения...", self.service.stop_runtime)
            self.notify("Подключение остановлено", severity="information")
            self._update_dashboard()
        except Exception:
            pass

    async def _action_diag(self) -> None:
        if self.service is None:
            return
        try:
            await self._run_service_action("Снятие диагностики...", self.service.capture_diagnostics)
            self.notify("Диагностика сохранена", severity="information")
            self._update_dashboard()
        except Exception:
            pass

    async def _do_import_subscription(self, result: dict[str, str] | None) -> None:
        if result is None or self.service is None:
            return
        try:
            await self._run_service_action(
                "Добавление подписки...",
                self.service.add_subscription,
                result["name"],
                result["url"],
            )
            self.notify("Подписка добавлена", severity="information")
            self._update_nodes()
            self._update_dashboard()
        except Exception as exc:
            print(f"ERROR _do_import_subscription: {exc}")
            import traceback
            traceback.print_exc()
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
        except Exception:
            pass

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
            await self._run_service_action(
                "Активация узла...",
                self.service.activate_selection,
                profile_id,
                node_id,
            )
            self.notify("Узел активирован", severity="information")
            self._update_dashboard()
            self._update_nodes()
        except Exception:
            pass

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
                self.service.ping_node_by_id,
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
            nodes_tab.selected_sub_id = None
            hint = nodes_tab.query_one("#nodes-hint", Label)
            hint.update("Выберите строку и нажмите действие")
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

    async def _action_activate_routing_profile(self) -> None:
        if self.service is None:
            return
        routing_tab = self.query_one("#routing-tab", RoutingTab)
        rp_id = routing_tab.selected_profile_id
        if not rp_id:
            self.notify("Сначала выберите профиль в таблице", severity="warning")
            return
        try:
            await self._run_service_action(
                "Активация профиля...",
                self.service.activate_routing_profile,
                rp_id,
            )
            self.notify("Профиль активирован", severity="information")
            self._update_routing()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка активации: {exc}", severity="error")

    async def _action_toggle_routing(self) -> None:
        if self.service is None:
            return
        try:
            store = self.service.ensure_store_ready()
            routing_state = store.get("routing", {})
            current = bool(routing_state.get("enabled", False))
            await self._run_service_action(
                "Переключение маршрутизации...",
                self.service.set_routing_enabled,
                not current,
            )
            state = "включена" if not current else "выключена"
            self.notify(f"Маршрутизация {state}", severity="information")
            self._update_routing()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка: {exc}", severity="error")

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

    async def _do_clear_routing_profile(self, confirmed: bool) -> None:
        if not confirmed or self.service is None:
            return
        try:
            await self._run_service_action(
                "Сброс профиля...",
                self.service.clear_active_routing_profile,
            )
            self.notify("Профиль сброшен", severity="information")
            self._update_routing()
            self._update_dashboard()
        except Exception as exc:
            self.notify(f"Ошибка сброса: {exc}", severity="error")

    def _action_clear_routing_profile(self) -> None:
        if self.service is None:
            return
        self.push_screen(ConfirmModal("Сбросить активный routing-профиль?"), callback=lambda c: asyncio.create_task(self._do_clear_routing_profile(c)))

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
        except Exception:
            pass

    def _stop_tray(self) -> None:
        """Остановить tray-процесс, если запущен."""
        # Tray-интеграция: при необходимости отправить сигнал процессу tui_tray.py
        pass

    def _start_tray(self) -> None:
        """Запустить tray-процесс в фоне."""
        # Tray-интеграция: запуск gui/tui_tray.py через subprocess
        pass

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
    app = SubvostTUI()
    app.run()


if __name__ == "__main__":
    main()
