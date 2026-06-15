#!/usr/bin/env python3
"""Тесты для tui_app.py: tray, автоактивация, обработка ошибок."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import unittest
import inspect
from pathlib import Path
from unittest.mock import MagicMock, call, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))


class SubvostTUITests(unittest.TestCase):
    """Тесты функциональности SubvostTUI."""

    def setUp(self) -> None:
        # Патчим все textual-зависимости на уровне модуля
        self.textual_patcher = patch.multiple(
            "tui_app",
            App=MagicMock(),
            Container=MagicMock(),
            Vertical=MagicMock(),
            Horizontal=MagicMock(),
            Grid=MagicMock(),
            Label=MagicMock(),
            Button=MagicMock(),
            DataTable=MagicMock(),
            Header=MagicMock(),
            Static=MagicMock(),
            TabPane=MagicMock(),
            TabbedContent=MagicMock(),
            RichLog=MagicMock(),
            Select=MagicMock(),
            Switch=MagicMock(),
            Input=MagicMock(),
            TextArea=MagicMock(),
            reactive=MagicMock(),
            ModalScreen=MagicMock(),
            Footer=MagicMock(),
            Screen=MagicMock(),
            ShellRuntimeAdapter=MagicMock(),
            SystemNetworkAdapter=MagicMock(),
            LoadingModal=MagicMock(side_effect=lambda msg="": MagicMock(message=msg)),
            ConfirmModal=MagicMock(),
            ImportSubscriptionModal=MagicMock(),
            ImportLinkModal=MagicMock(),
            ImportRoutingProfileModal=MagicMock(),
            JsonNodeRepository=MagicMock(),
            JsonSubscriptionRepository=MagicMock(),
        )
        self.textual_patcher.start()

        self.mock_service = MagicMock()
        from tui_app import SubvostTUI

        self.app = SubvostTUI(service=self.mock_service)
        # Патчим методы, которые требуют реального textual App
        self.app._update_dashboard = MagicMock()
        self.app._update_nodes = MagicMock()
        # Патчим notify, так как это родительский метод из App
        self.app.notify = MagicMock()
        # Настраиваем push_screen / pop_screen / is_screen_installed для тестов модальных окон
        from unittest.mock import AsyncMock
        self.app.push_screen = AsyncMock()
        self.app.pop_screen = MagicMock()
        self.app.is_screen_installed = MagicMock(return_value=True)

    def tearDown(self) -> None:
        self.textual_patcher.stop()

    # ─── 10f: Автоактивация ─────────────────────────────────────────

    def test_auto_activate_first_node_selects_first_enabled(self) -> None:
        """Автоактивация выбирает первый enabled-узел при пустом active_selection."""
        store = {
            "active_selection": {},
            "profiles": [
                {
                    "id": "prof-1",
                    "name": "Profile 1",
                    "enabled": True,
                    "nodes": [
                        {"id": "node-1", "name": "Node 1", "enabled": True},
                    ],
                },
            ],
        }
        self.mock_service.ensure_store_ready.return_value = store

        asyncio.run(self.app._auto_activate_first_node())

        from tui_app import JsonNodeRepository

        repo_instance = JsonNodeRepository.return_value
        repo_instance.activate.assert_called_once_with("prof-1", "node-1")
        self.mock_service.persist_store.assert_called_once_with(store)
        self.app.notify.assert_called_with(
            "Автоматически активирован узел: Node 1",
            severity="information",
        )

    def test_auto_activate_skips_when_selection_exists(self) -> None:
        """Автоактивация не трогает active_selection, если она уже установлена."""
        store = {
            "active_selection": {"profile_id": "prof-1", "node_id": "node-2"},
            "profiles": [
                {
                    "id": "prof-1",
                    "nodes": [
                        {"id": "node-1", "name": "Node 1"},
                        {"id": "node-2", "name": "Node 2"},
                    ],
                },
            ],
        }
        self.mock_service.ensure_store_ready.return_value = store

        asyncio.run(self.app._auto_activate_first_node())

        from tui_app import JsonNodeRepository

        repo_instance = JsonNodeRepository.return_value
        repo_instance.activate.assert_not_called()

    def test_auto_activate_skips_disabled_nodes(self) -> None:
        """Автоактивация пропускает disabled-узлы и профили."""
        store = {
            "active_selection": {},
            "profiles": [
                {
                    "id": "prof-1",
                    "enabled": False,
                    "nodes": [
                        {"id": "node-1", "enabled": True},
                    ],
                },
                {
                    "id": "prof-2",
                    "enabled": True,
                    "nodes": [
                        {"id": "node-2", "enabled": False},
                        {"id": "node-3", "enabled": True},
                    ],
                },
            ],
        }
        self.mock_service.ensure_store_ready.return_value = store

        asyncio.run(self.app._auto_activate_first_node())

        from tui_app import JsonNodeRepository

        repo_instance = JsonNodeRepository.return_value
        repo_instance.activate.assert_called_once_with("prof-2", "node-3")

    def test_auto_activate_does_nothing_when_no_nodes(self) -> None:
        """Автоактивация ничего не делает при пустом profiles."""
        store = {"active_selection": {}, "profiles": []}
        self.mock_service.ensure_store_ready.return_value = store

        asyncio.run(self.app._auto_activate_first_node())

        from tui_app import JsonNodeRepository

        repo_instance = JsonNodeRepository.return_value
        repo_instance.activate.assert_not_called()

    # ─── 10g: Tray ───────────────────────────────────────────────────

    def test_start_tray_launches_subprocess(self) -> None:
        """_start_tray запускает tui_tray.py через subprocess.Popen."""
        with (
            patch("tui_app.subprocess.Popen") as mock_popen,
            patch("tui_app.SCRIPT_DIR") as mock_script_dir,
        ):
            mock_tray_path = MagicMock(spec=["__str__", "exists"])
            mock_tray_path.__str__ = MagicMock(return_value="/mock/path/tui_tray.py")
            mock_tray_path.exists = MagicMock(return_value=True)
            mock_script_dir.__truediv__.return_value = mock_tray_path

            self.app._start_tray()

            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0][0], sys.executable)
            self.assertIn("tui_tray.py", args[0][1])
            self.assertIs(kwargs.get("stdout"), subprocess.DEVNULL)
            self.assertIs(kwargs.get("stderr"), subprocess.DEVNULL)
            self.assertTrue(kwargs.get("start_new_session"))

    def test_start_tray_skips_when_missing(self) -> None:
        """_start_tray ничего не делает, если tui_tray.py не существует."""
        with (
            patch("tui_app.subprocess.Popen") as mock_popen,
            patch("tui_app.SCRIPT_DIR") as mock_script_dir,
        ):
            mock_script_dir.__truediv__.return_value = Path("/nonexistent")
            mock_script_dir.exists.return_value = False

            self.app._start_tray()
            mock_popen.assert_not_called()

    def test_stop_tray_kills_processes(self) -> None:
        """_stop_tray убивает процессы tui_tray.py через os.kill."""
        with patch("tui_app.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "12345\n67890\n"

            with (
                patch("tui_app.os.kill") as mock_kill,
                patch("tui_app.os.getpid", return_value=99999),
            ):
                self.app._stop_tray()

                mock_kill.assert_has_calls([
                    call(12345, signal.SIGTERM),
                    call(67890, signal.SIGTERM),
                ], any_order=True)

    def test_stop_tray_skips_own_pid(self) -> None:
        """_stop_tray не убивает собственный PID."""
        with patch("tui_app.subprocess.run") as mock_run:
            mock_run.return_value.stdout = f"{os.getpid()}\n12345\n"

            with patch("tui_app.os.kill") as mock_kill:
                self.app._stop_tray()
                mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_stop_tray_ignores_pgrep_failure(self) -> None:
        """_stop_tray молча глотает CalledProcessError."""
        with patch("tui_app.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "pgrep")
            self.app._stop_tray()  # не должно быть исключения

    # ─── 10h: Обработка ошибок в action-методах ──────────────────────

    def test_action_start_shows_error(self) -> None:
        """_action_start показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("start failed"))
        asyncio.run(self.app._action_start())
        self.app.notify.assert_any_call("start failed", severity="error")

    def test_action_stop_shows_error(self) -> None:
        """_action_stop показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("stop failed"))
        asyncio.run(self.app._action_stop())
        self.app.notify.assert_any_call("stop failed", severity="error")

    def test_action_diag_shows_error(self) -> None:
        """_action_diag показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("diag failed"))
        asyncio.run(self.app._action_diag())
        self.app.notify.assert_any_call("diag failed", severity="error")

    def test_action_cleanup_shows_error(self) -> None:
        """_action_cleanup показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("cleanup failed"))
        asyncio.run(self.app._action_cleanup())
        self.app.notify.assert_any_call("cleanup failed", severity="error")

    # ─── 10i: Модальное окно загрузки ───────────────────────────────

    def test_show_loading_pushes_modal_and_returns_it(self) -> None:
        """_show_loading пушит LoadingModal и возвращает его."""
        async def run():
            return await self.app._show_loading("Тестовое сообщение")

        modal = asyncio.run(run())

        from tui_app import LoadingModal
        # LoadingModal создан с правильным сообщением
        LoadingModal.assert_called_once_with("Тестовое сообщение")
        # push_screen вызван ровно один раз — с тем же объектом, что вернул LoadingModal
        self.app.push_screen.assert_awaited_once()
        pushed_arg = self.app.push_screen.await_args[0][0]
        # возвращаемое значение _show_loading — то же модальное окно, что передано в push_screen
        self.assertIs(modal, pushed_arg)
    def test_hide_loading_pops_when_screen_installed(self) -> None:
        """_hide_loading вызывает pop_screen когда экран установлен."""
        modal = MagicMock()
        self.app.is_screen_installed.return_value = True

        self.app._hide_loading(modal)

        self.app.is_screen_installed.assert_called_once_with(modal)
        self.app.pop_screen.assert_called_once()

    def test_hide_loading_skips_when_screen_not_installed(self) -> None:
        """_hide_loading не вызывает pop_screen когда экран не установлен."""
        modal = MagicMock()
        self.app.is_screen_installed.return_value = False

        self.app._hide_loading(modal)

        self.app.is_screen_installed.assert_called_once_with(modal)
        self.app.pop_screen.assert_not_called()

    def test_hide_loading_none_is_noop(self) -> None:
        """_hide_loading(None) не падает и ничего не делает."""
        self.app._hide_loading(None)
        self.app.is_screen_installed.assert_not_called()
        self.app.pop_screen.assert_not_called()

    def test_hide_loading_swallows_pop_exception(self) -> None:
        """_hide_loading глотает исключение из pop_screen."""
        modal = MagicMock()
        self.app.is_screen_installed.return_value = True
        self.app.pop_screen.side_effect = RuntimeError("stack error")

        # Не должно быть исключения
        self.app._hide_loading(modal)

        self.app.pop_screen.assert_called_once()

    def test_run_service_action_opens_and_closes_modal(self) -> None:
        """_run_service_action показывает окно до действия и скрывает после."""
        action = MagicMock(return_value="result")

        async def run():
            return await self.app._run_service_action("Тест...", action, "arg1", kw="val")

        result = asyncio.run(run())

        self.assertEqual(result, "result")
        # push_screen был вызван (через _show_loading)
        self.app.push_screen.assert_awaited_once()
        # pop_screen был вызван (через _hide_loading)
        self.app.pop_screen.assert_called_once()
        # Действие выполнено с правильными аргументами
        action.assert_called_once_with("arg1", kw="val")

    def test_run_service_action_closes_modal_on_exception(self) -> None:
        """_hide_loading вызывается даже если действие упало с исключением."""
        action = MagicMock(side_effect=ValueError("boom"))

        async def run():
            await self.app._run_service_action("Тест...", action)

        with self.assertRaises(ValueError):
            asyncio.run(run())

        # pop_screen всё равно вызван (finally)
        self.app.pop_screen.assert_called_once()
        self.app.notify.assert_called_with("boom", severity="error")

    def test_two_parallel_actions_use_separate_modals(self) -> None:
        """Два параллельных _run_service_action не перезаписывают модальные окна."""
        action1 = MagicMock(return_value="r1")
        action2 = MagicMock(return_value="r2")

        async def run_both():
            return await asyncio.gather(
                self.app._run_service_action("A", action1),
                self.app._run_service_action("B", action2),
            )

        results = asyncio.run(run_both())

        self.assertEqual(results, ["r1", "r2"])
        # push_screen вызван дважды (по одному на каждое действие)
        self.assertEqual(self.app.push_screen.await_count, 2)
        # pop_screen вызван дважды
        self.assertEqual(self.app.pop_screen.call_count, 2)

    def test_run_service_action_timeout_closes_modal(self) -> None:
        """_hide_loading вызывается после таймаута _run_service_action."""
        async def run():
            await self.app._run_service_action("Тест...", MagicMock())

        with patch("tui_app.asyncio.wait_for", side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                asyncio.run(run())

        # pop_screen всё равно вызван (finally)
        self.app.pop_screen.assert_called_once()
        self.app.notify.assert_called_with(
            "Действие 'Тест...' превысило таймаут (120 с).",
            severity="error",
        )

    def test_action_start_resets_flag_on_timeout_error(self) -> None:
        """_action_start сбрасывает _action_in_progress при TimeoutError."""
        self.app._run_service_action = MagicMock(side_effect=TimeoutError())
        asyncio.run(self.app._action_start())
        self.assertFalse(self.app._action_in_progress)

    # ─── 10j: Guard _action_in_progress ───────────────────────────────

    def test_action_start_blocked_when_action_in_progress(self) -> None:
        """_action_start с _action_in_progress=True показывает предупреждение."""
        self.app._action_in_progress = True
        self.app._run_service_action = MagicMock()

        asyncio.run(self.app._action_start())

        self.app._run_service_action.assert_not_called()
        self.app.notify.assert_called_with(
            "Действие уже выполняется, подождите...", severity="warning"
        )

    def test_action_stop_blocked_when_action_in_progress(self) -> None:
        """_action_stop с _action_in_progress=True показывает предупреждение."""
        self.app._action_in_progress = True
        self.app._run_service_action = MagicMock()

        asyncio.run(self.app._action_stop())

        self.app._run_service_action.assert_not_called()
        self.app.notify.assert_called_with(
            "Действие уже выполняется, подождите...", severity="warning"
        )

    def test_action_start_resets_flag_in_finally(self) -> None:
        """_action_start сбрасывает _action_in_progress даже при ошибке."""
        self.app._run_service_action = MagicMock(side_effect=Exception("fail"))

        asyncio.run(self.app._action_start())

        self.assertFalse(self.app._action_in_progress)

    def test_action_stop_resets_flag_in_finally(self) -> None:
        """_action_stop сбрасывает _action_in_progress даже при ошибке."""
        self.app._run_service_action = MagicMock(side_effect=Exception("fail"))

        asyncio.run(self.app._action_stop())

        self.assertFalse(self.app._action_in_progress)

    def test_action_refresh_all_shows_error(self) -> None:
        """_action_refresh_all показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("refresh failed"))
        asyncio.run(self.app._action_refresh_all())
        self.app.notify.assert_any_call("refresh failed", severity="error")

    # ─── 10k: Проверка результата pkexec в _action_start / _action_stop ──


    def test_action_start_notifies_success_when_last_action_ok(self) -> None:
        """_action_start с ok=True показывает 'Подключение запущено'."""
        from unittest.mock import AsyncMock
        self.app._run_service_action = AsyncMock(
            return_value={"last_action": {"ok": True}}
        )
        asyncio.run(self.app._action_start())
        self.app.notify.assert_called_with(
            "Подключение запущено", severity="information"
        )

    def test_action_start_notifies_warning_when_last_action_not_ok(self) -> None:
        """_action_start с ok=False показывает предупреждение с message."""
        from unittest.mock import AsyncMock
        self.app._run_service_action = AsyncMock(
            return_value={"last_action": {"ok": False, "message": "Запуск завершился ошибкой, код 126."}}
        )
        asyncio.run(self.app._action_start())
        self.app.notify.assert_called_with(
            "Запуск завершился ошибкой, код 126.", severity="warning"
        )

    def test_action_stop_notifies_success_when_last_action_ok(self) -> None:
        """_action_stop с ok=True показывает 'Подключение остановлено'."""
        from unittest.mock import AsyncMock
        self.app._run_service_action = AsyncMock(
            return_value={"last_action": {"ok": True}}
        )
        asyncio.run(self.app._action_stop())
        self.app.notify.assert_called_with(
            "Подключение остановлено", severity="information"
        )

    def test_action_stop_notifies_warning_when_last_action_not_ok(self) -> None:
        """_action_stop с ok=False показывает предупреждение с message."""
        from unittest.mock import AsyncMock
        self.app._run_service_action = AsyncMock(
            return_value={"last_action": {"ok": False, "message": "Остановка завершилась ошибкой, код 126."}}
        )
        asyncio.run(self.app._action_stop())
        self.app.notify.assert_called_with(
            "Остановка завершилась ошибкой, код 126.", severity="warning"
        )


if __name__ == "__main__":
    unittest.main()


class SettingsTabTests(unittest.TestCase):
    """Структурные тесты SettingsTab (виджеты обновления xray)."""

    def test_settings_tab_compose_contains_xray_section(self) -> None:
        """Проверка, что compose содержит версионные метки и кнопки xray."""
        from tui_app import SettingsTab
        tab_source = inspect.getsource(SettingsTab.compose)
        self.assertIn("lbl-xray-version", tab_source)
        self.assertIn("lbl-xray-latest", tab_source)
        self.assertIn("btn-check-updates", tab_source)
        self.assertIn("btn-update-xray", tab_source)
        self.assertIn("Ядро Xray", tab_source)

    def test_settings_tab_css_contains_xray_actions_selector(self) -> None:
        """Проверка, что CSS содержит селектор #xray-update-actions."""
        from tui_app import SubvostTUI
        self.assertIn("#xray-update-actions", SubvostTUI.CSS)

    def test_settings_tab_compose_contains_xray_buttons_in_handler(self) -> None:
        """Проверка, что on_button_pressed обрабатывает кнопки xray."""
        from tui_app import SettingsTab
        handler_source = inspect.getsource(SettingsTab.on_button_pressed)
        self.assertIn("btn-check-updates", handler_source)
        self.assertIn("_action_check_xray_updates", handler_source)
        self.assertIn("btn-update-xray", handler_source)
        self.assertIn("_action_update_xray", handler_source)


class TuiLockTests(unittest.TestCase):
    """Тесты per-bundle lock механизма TUI."""

    def test_lock_path_is_per_bundle(self) -> None:
        from tui_app import TUI_LOCK_PATH, PROJECT_ROOT
        self.assertTrue(
            str(TUI_LOCK_PATH).startswith(str(PROJECT_ROOT)),
            f"Lock должен быть внутри bundle: {TUI_LOCK_PATH}",
        )

    def test_old_lock_path_is_in_config_home(self) -> None:
        from tui_app import OLD_TUI_LOCK_PATH
        self.assertIn(".config", str(OLD_TUI_LOCK_PATH))

    def test_lock_conflict_modal_contains_expected_widgets(self) -> None:
        from tui_app import TuiLockConflictModal
        source = inspect.getsource(TuiLockConflictModal.compose)
        self.assertIn("btn-lock-replace", source)
        self.assertIn("btn-lock-cancel", source)
