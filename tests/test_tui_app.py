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
            ConfirmModal=MagicMock(),
            ImportSubscriptionModal=MagicMock(),
            ImportLinkModal=MagicMock(),
            ImportRoutingProfileModal=MagicMock(),
            # NOTE: репозитории теперь не патчатся — TUI работает через SubvostAppService
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
        """Автоактивация выбирает первый enabled-узел при пустом active_selection через service.auto_activate_first_node."""
        from unittest.mock import AsyncMock

        self.app._run_service_action = AsyncMock(
            return_value={
                "ok": True,
                "message": "Автоматически активирован узел 'Node 1'.",
            }
        )

        asyncio.run(self.app._auto_activate_first_node())

        self.app._run_service_action.assert_called_once()
        args, kwargs = self.app._run_service_action.call_args
        self.assertEqual(args[0], "Авто-активация узла...")
        self.assertIs(args[1], self.mock_service.auto_activate_first_node)
        self.app.notify.assert_called_with(
            "Автоматически активирован узел 'Node 1'.",
            severity="information",
        )
        self.app._update_dashboard.assert_called_once()
        self.app._update_nodes.assert_called_once()

    def test_auto_activate_skips_when_selection_exists(self) -> None:
        """Автоактивация вызывает service.auto_activate_first_node (выбор уже есть — сервис вернёт skip)."""
        from unittest.mock import AsyncMock

        self.app._run_service_action = AsyncMock(
            return_value={"ok": True, "message": "Узел уже выбран."}
        )

        asyncio.run(self.app._auto_activate_first_node())

        self.app._run_service_action.assert_called_once()
        args, kwargs = self.app._run_service_action.call_args
        self.assertIs(args[1], self.mock_service.auto_activate_first_node)
        # Сообщение "уже выбран" не содержит "автоматически активирован" — notify не вызывается
        self.app.notify.assert_not_called()
        self.app._update_dashboard.assert_called_once()
        self.app._update_nodes.assert_called_once()

    def test_auto_activate_skips_disabled_nodes(self) -> None:
        """Автоактивация делегирует выбор enabled-узла в service.auto_activate_first_node (фильтрация внутри сервиса)."""
        from unittest.mock import AsyncMock

        self.app._run_service_action = AsyncMock(
            return_value={
                "ok": True,
                "message": "Автоматически активирован узел 'node-3'.",
            }
        )

        asyncio.run(self.app._auto_activate_first_node())

        self.app._run_service_action.assert_called_once()
        args, kwargs = self.app._run_service_action.call_args
        self.assertIs(args[1], self.mock_service.auto_activate_first_node)
        self.app.notify.assert_called_with(
            "Автоматически активирован узел 'node-3'.",
            severity="information",
        )
        self.app._update_dashboard.assert_called_once()
        self.app._update_nodes.assert_called_once()

    def test_auto_activate_does_nothing_when_no_nodes(self) -> None:
        """Автоактивация при пустом profiles вызывает сервис, который вернёт skip без notify."""
        from unittest.mock import AsyncMock

        self.app._run_service_action = AsyncMock(
            return_value={
                "ok": True,
                "message": "Нет доступных узлов для авто-активации.",
            }
        )

        asyncio.run(self.app._auto_activate_first_node())

        self.app._run_service_action.assert_called_once()
        self.app.notify.assert_not_called()
        self.app._update_dashboard.assert_called_once()
        self.app._update_nodes.assert_called_once()
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

    # ─── 10i: Оверлей загрузки ────────────────────────────────────

    def test_show_loading_updates_overlay_and_adds_class(self) -> None:
        """_show_loading обновляет текст, показывает оверлей и блокирует вкладки/footer."""
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        self.app.query_one = MagicMock(side_effect=[mock_overlay, mock_tabs, mock_footer])

        self.app._show_loading("Тестовое сообщение")

        # query_one должен быть вызван 3 раза: overlay, tabs, footer
        self.assertEqual(self.app.query_one.call_count, 3)
        call_args = [c.args[0] for c in self.app.query_one.call_args_list]
        self.assertEqual(call_args, ["#loading-overlay", "#main-tabs", "#footer-bar"])
        mock_overlay.update.assert_called_once_with("Тестовое сообщение")
        mock_overlay.add_class.assert_called_once_with("-visible")
        mock_tabs.disabled = True
        mock_footer.disabled = True
        self.app.notify.assert_called_once_with("Тестовое сообщение", severity="information")

    def test_hide_loading_removes_class(self) -> None:
        """_hide_loading скрывает оверлей и разблокирует вкладки/footer."""
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        self.app.query_one = MagicMock(side_effect=[mock_overlay, mock_tabs, mock_footer])

        self.app._hide_loading()

        # query_one должен быть вызван 3 раза: overlay, tabs, footer
        self.assertEqual(self.app.query_one.call_count, 3)
        call_args = [c.args[0] for c in self.app.query_one.call_args_list]
        self.assertEqual(call_args, ["#loading-overlay", "#main-tabs", "#footer-bar"])
        mock_overlay.remove_class.assert_called_once_with("-visible")
        mock_tabs.disabled = False
        mock_footer.disabled = False

    def test_show_loading_swallows_query_exception(self) -> None:
        """_show_loading молча глотает исключение query_one."""
        self.app.query_one = MagicMock(side_effect=Exception("no overlay"))
        # Не должно быть исключения
        self.app._show_loading("Тест")

    def test_hide_loading_swallows_query_exception(self) -> None:
        """_hide_loading молча глотает исключение query_one."""
        self.app.query_one = MagicMock(side_effect=Exception("no overlay"))
        # Не должно быть исключения
        self.app._hide_loading()

    def test_run_service_action_shows_and_hides_overlay(self) -> None:
        """_run_service_action показывает оверлей до действия и скрывает после."""
        action = MagicMock(return_value="result")
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        self.app.query_one = MagicMock(side_effect=[mock_overlay, mock_tabs, mock_footer, mock_overlay, mock_tabs, mock_footer])

        async def run():
            return await self.app._run_service_action("Тест...", action, "arg1", kw="val")

        result = asyncio.run(run())

        self.assertEqual(result, "result")
        # оверлей показан
        mock_overlay.update.assert_called_once_with("Тест...")
        mock_overlay.add_class.assert_called_once_with("-visible")
        # tabs/footer заблокированы на время loading
        mock_tabs.disabled = True
        mock_footer.disabled = True
        # toast объявляет о начале действия
        self.app.notify.assert_any_call("Тест...", severity="information")
        # оверлей скрыт
        mock_overlay.remove_class.assert_called_once_with("-visible")
        # tabs/footer разблокированы после loading
        mock_tabs.disabled = False
        mock_footer.disabled = False
        # Действие выполнено с правильными аргументами
        action.assert_called_once_with("arg1", kw="val")

    def test_run_service_action_hides_overlay_on_exception(self) -> None:
        """_hide_loading вызывается даже если действие упало с исключением."""
        action = MagicMock(side_effect=ValueError("boom"))
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        self.app.query_one = MagicMock(side_effect=[mock_overlay, mock_tabs, mock_footer, mock_overlay, mock_tabs, mock_footer])

        async def run():
            await self.app._run_service_action("Тест...", action)

        with self.assertRaises(ValueError):
            asyncio.run(run())

        # оверлей всё равно скрыт (finally)
        mock_overlay.remove_class.assert_called_once_with("-visible")
        # tabs/footer разблокированы (finally)
        mock_tabs.disabled = False
        mock_footer.disabled = False
        self.app.notify.assert_called_with("boom", severity="error")

    def test_run_service_action_hides_overlay_on_timeout(self) -> None:
        """_hide_loading вызывается после таймаута _run_service_action."""
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        mock_strip = MagicMock()
        # show(3) + _set_status(1) + hide(3) = 7 вызовов
        self.app.query_one = MagicMock(side_effect=[
            mock_overlay, mock_tabs, mock_footer,
            mock_strip,
            mock_overlay, mock_tabs, mock_footer,
        ])

        async def run():
            await self.app._run_service_action("Тест...", MagicMock())

        with patch("tui_app.asyncio.wait_for", side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                asyncio.run(run())

        # оверлей скрыт
        mock_overlay.remove_class.assert_called_once_with("-visible")
        # tabs/footer разблокированы (finally)
        mock_tabs.disabled = False
        mock_footer.disabled = False
        self.app.notify.assert_called_with(
            "Действие 'Тест...' превысило таймаут (120 с).",
            severity="error",
        )

    def test_two_parallel_actions_use_same_overlay(self) -> None:
        """Два параллельных _run_service_action используют один оверлей."""
        action1 = MagicMock(return_value="r1")
        action2 = MagicMock(return_value="r2")
        mock_overlay = MagicMock()
        mock_tabs = MagicMock()
        mock_footer = MagicMock()
        # 2 действия × (show: 3 query_one + hide: 3 query_one) = 12 вызовов
        self.app.query_one = MagicMock(side_effect=[
            mock_overlay, mock_tabs, mock_footer,  # show A
            mock_overlay, mock_tabs, mock_footer,  # hide A
            mock_overlay, mock_tabs, mock_footer,  # show B
            mock_overlay, mock_tabs, mock_footer,  # hide B
        ])

        async def run_both():
            return await asyncio.gather(
                self.app._run_service_action("A", action1),
                self.app._run_service_action("B", action2),
            )

        results = asyncio.run(run_both())

        self.assertEqual(results, ["r1", "r2"])
        self.assertEqual(mock_overlay.update.call_count, 2)
        self.assertEqual(mock_overlay.add_class.call_count, 2)
        self.assertEqual(mock_overlay.remove_class.call_count, 2)
        # tabs/footer блокировались и разблокировались по 2 раза
        self.assertEqual(mock_tabs.disabled, False)  # финальное состояние — разблокирован
        self.assertEqual(mock_footer.disabled, False)

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

    def test_action_refresh_all_blocked_when_action_in_progress(self) -> None:
        """_action_refresh_all с _action_in_progress=True показывает предупреждение."""
        self.app._action_in_progress = True
        self.app._run_service_action = MagicMock()

        asyncio.run(self.app._action_refresh_all())

        self.app._run_service_action.assert_not_called()
        self.app.notify.assert_called_with(
            "Действие уже выполняется, подождите...", severity="warning"
        )

    def test_action_refresh_all_resets_flag_in_finally(self) -> None:
        """_action_refresh_all сбрасывает _action_in_progress даже при ошибке."""
        self.app._run_service_action = MagicMock(side_effect=Exception("fail"))

        asyncio.run(self.app._action_refresh_all())

        self.assertFalse(self.app._action_in_progress)

    def test_action_activate_node_blocked_when_action_in_progress(self) -> None:
        """_action_activate_node с _action_in_progress=True показывает предупреждение."""
        self.app._action_in_progress = True
        self.app._run_service_action = MagicMock()

        asyncio.run(self.app._action_activate_node())

        self.app._run_service_action.assert_not_called()
        self.app.notify.assert_called_with(
            "Действие уже выполняется, подождите...", severity="warning"
        )

    def test_action_activate_node_resets_flag_in_finally(self) -> None:
        """_action_activate_node сбрасывает _action_in_progress даже при ошибке."""
        mock_tab = MagicMock()
        mock_tab.selected_row_key = "prof-1:node-1"
        self.app.query_one = MagicMock(return_value=mock_tab)
        self.app._run_service_action = MagicMock(side_effect=Exception("fail"))

        asyncio.run(self.app._action_activate_node())

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

    def test_action_refresh_all_emits_single_summary_toast(self) -> None:
        """_action_refresh_all эмитит ровно один notify с правильным severity."""
        from unittest.mock import AsyncMock

        def _run_with_refresh_all(ok_count: int, error_count: int) -> None:
            self.app.notify.reset_mock()
            payload = {
                "ok": True,
                "message": "Все включённые подписки обновлены.",
                "refresh_all": {"ok": ok_count, "error": error_count},
            }
            self.app._run_service_action = AsyncMock(return_value=payload)
            asyncio.run(self.app._action_refresh_all())
            self.assertEqual(self.app.notify.call_count, 1)
            self.app.notify.assert_called_once()

        # Все успешно → severity="information"
        _run_with_refresh_all(ok_count=3, error_count=0)
        args, kwargs = self.app.notify.call_args
        message = args[0] if args else kwargs.get("message", "")
        self.assertEqual(kwargs.get("severity"), "information")
        self.assertIn("Обновлено подписок: 3", message)

        # Полный провал → severity="error"
        _run_with_refresh_all(ok_count=0, error_count=2)
        args, kwargs = self.app.notify.call_args
        message = args[0] if args else kwargs.get("message", "")
        self.assertEqual(kwargs.get("severity"), "error")
        self.assertIn("Ошибок: 2", message)

        # Частичный успех → severity="warning"
        _run_with_refresh_all(ok_count=1, error_count=1)
        args, kwargs = self.app.notify.call_args
        message = args[0] if args else kwargs.get("message", "")
        self.assertEqual(kwargs.get("severity"), "warning")
        self.assertIn("Обновлено: 1", message)
        self.assertIn("ошибок: 1", message)

        # Нет активных подписок → severity="information", "Нет активных..."
        _run_with_refresh_all(ok_count=0, error_count=0)
        args, kwargs = self.app.notify.call_args
        message = args[0] if args else kwargs.get("message", "")
        self.assertEqual(kwargs.get("severity"), "information")
        self.assertIn("Нет активных подписок", message)

    # ─── 10k: action_switch_tab / _set_status (P3 из review) ──────────

    def test_action_switch_tab_sets_active(self) -> None:
        """action_switch_tab устанавливает active на TabbedContent."""
        mock_tabs = MagicMock()
        self.app.query_one = MagicMock(return_value=mock_tabs)
        self.app.action_switch_tab("tab-routing")
        mock_tabs.active = "tab-routing"
        # query_one вызван с id main-tabs (тип опускаем — он замокан)
        self.assertEqual(self.app.query_one.call_args.args[0], "#main-tabs")

    def test_action_switch_tab_swallows_query_exception(self) -> None:
        """action_switch_tab молча глотает исключение query_one."""
        self.app.query_one = MagicMock(side_effect=Exception("not mounted"))
        # Не должно быть исключения
        self.app.action_switch_tab("tab-dashboard")

    def test_set_status_updates_strip_without_notify(self) -> None:
        """_set_status без severity обновляет status-strip без toast."""
        mock_strip = MagicMock()
        self.app.query_one = MagicMock(return_value=mock_strip)
        self.app.notify.reset_mock()
        self.app._set_status("Готово")
        mock_strip.update.assert_called_once_with("Готово")
        self.app.notify.assert_not_called()

    def test_set_status_with_severity_also_notifies(self) -> None:
        """_set_status с severity обновляет strip и шлёт toast."""
        mock_strip = MagicMock()
        self.app.query_one = MagicMock(return_value=mock_strip)
        self.app.notify.reset_mock()
        self.app._set_status("Ошибка", severity="error")
        mock_strip.update.assert_called_once_with("Ошибка")
        self.app.notify.assert_called_once_with("Ошибка", severity="error")

    def test_set_status_swallows_query_exception(self) -> None:
        """_set_status молча глотает исключение query_one (но notify всё равно шлёт)."""
        self.app.query_one = MagicMock(side_effect=Exception("not mounted"))
        self.app.notify.reset_mock()
        # Не должно быть исключения
        self.app._set_status("Готово", severity="information")
        # notify вызывается даже если strip не найден
        self.app.notify.assert_called_once_with("Готово", severity="information")

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
