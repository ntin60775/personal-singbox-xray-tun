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
            LoadingModal=MagicMock(),
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

    def test_action_refresh_all_shows_error(self) -> None:
        """_action_refresh_all показывает ошибку при исключении."""
        self.app._run_service_action = MagicMock(side_effect=Exception("refresh failed"))
        asyncio.run(self.app._action_refresh_all())
        self.app.notify.assert_any_call("refresh failed", severity="error")


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
