from __future__ import annotations

import base64
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

import gui_server  # noqa: E402
import gui_contract  # noqa: E402
from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import add_subscription, ensure_store_initialized, refresh_subscription, save_store  # noqa: E402


class FakeResponse:
    def __init__(self, payload: bytes, headers: dict[str, str] | None = None, status: int = 200) -> None:
        self._payload = payload
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class GuiServerRuntimeSelectionTests(unittest.TestCase):
    def main_html(self) -> str:
        return gui_server.load_gui_asset(gui_server.MAIN_GUI_ASSET)

    def test_gui_server_uses_shared_contract_version(self) -> None:
        self.assertEqual(gui_server.GUI_VERSION, gui_contract.GUI_VERSION)
        self.assertEqual(gui_contract.GUI_VERSION, "2026-04-08-main-gui-sidebar-v1")

    def test_main_gui_html_is_loaded_from_single_asset(self) -> None:
        html = self.main_html()
        self.assertEqual(gui_server.load_main_gui_html(), html)
        self.assertIn("function normalizeDataAttrName(name)", html)
        self.assertIn("function setHtmlIfChanged(element, markup, cacheKey = \"\")", html)
        self.assertIn("renderCache", html)
        self.assertIn("setHtmlIfChanged(els.nodeList, markup, \"nodes\")", html)
        self.assertIn('data-${normalizeDataAttrName(key)}="${escapeAttr(value)}"', html)
        self.assertNotIn('data-${key}="${escapeAttr(value)}"', html)

    def test_root_route_reads_main_gui_asset_at_request_time(self) -> None:
        do_get_source = inspect.getsource(gui_server.Handler.do_GET)
        self.assertIn("self.send_html(load_main_gui_html())", do_get_source)
        self.assertNotIn("self.send_html(INDEX_HTML)", do_get_source)

    def test_main_gui_asset_contains_operational_controls(self) -> None:
        self.assertEqual(gui_server.MAIN_GUI_ASSET, "main_gui.html")
        html = self.main_html()
        self.assertIn('id="main-gui-shell"', html)
        self.assertIn("Subvost Xray TUN", html)
        self.assertIn('id="start-button"', html)
        self.assertIn('id="diag-button"', html)
        self.assertIn('id="subscription-url"', html)
        self.assertIn('id="subscription-list"', html)
        self.assertIn('id="node-list"', html)
        self.assertIn('id="routing-form"', html)
        self.assertIn('id="routing-profile-list"', html)
        self.assertIn('id="routing-toggle-button"', html)
        self.assertIn('id="log-list"', html)
        self.assertIn('id="refresh-all-button"', html)
        self.assertIn('id="panel-log"', html)
        self.assertIn('id="panel-subscriptions"', html)
        self.assertIn('id="panel-nodes"', html)
        self.assertIn('id="view-stack"', html)
        self.assertIn('id="view-connection"', html)
        self.assertIn('id="view-routing"', html)
        self.assertIn('id="view-logs"', html)
        self.assertIn('data-view-nav="connection"', html)
        self.assertIn('data-view-nav="routing"', html)
        self.assertIn('data-view-nav="logs"', html)
        self.assertIn('id="view-title"', html)
        self.assertIn('id="nav-routing-meta"', html)
        self.assertIn('id="nav-logs-meta"', html)
        self.assertIn('id="connection-chip"', html)
        self.assertIn('id="connection-value"', html)
        self.assertIn('id="node-help-toggle"', html)
        self.assertIn('id="log-help-toggle"', html)
        self.assertIn('id="error-banner-dismiss"', html)
        self.assertIn("Клик по плитке сразу активирует узел.", html)
        self.assertIn("Ошибки всегда видны явно.", html)
        self.assertIn("Время подключения", html)
        self.assertIn('fetch("/api/store"', html)
        self.assertIn('"/api/nodes/ping"', html)
        self.assertIn('rel="icon"', html)
        self.assertIn('/assets/subvost-xray-tun-icon.svg', html)
        self.assertIn('id="sidebar-nav"', html)
        self.assertNotIn('id="profile-list"', html)
        self.assertNotIn('id="logging-toggle"', html)
        self.assertNotIn('id="command-output"', html)
        self.assertNotIn("Активный маршрут", html)
        self.assertNotIn("Состояние стека", html)
        self.assertNotIn("Ручной импорт ссылок", html)

    def test_main_gui_shell_uses_available_window_width(self) -> None:
        html = self.main_html()
        self.assertIn("width: 100%;", html)
        self.assertIn("max-width: 1280px;", html)
        self.assertIn("grid-template-columns: 248px minmax(0, 1fr);", html)
        self.assertIn("grid-template-rows: auto auto minmax(0, 1fr);", html)
        self.assertIn("grid-template-columns: minmax(292px, 348px) minmax(0, 1fr);", html)
        self.assertNotIn("width: min(100%, 1200px);", html)
        self.assertNotIn("grid-template-rows: auto minmax(0, 1fr) minmax(180px, 24dvh);", html)
        self.assertNotIn("grid-template-columns: minmax(280px, 340px) minmax(0, 1fr) minmax(300px, 360px);", html)
        self.assertNotIn('class="workspace-main"', html)

    def test_main_gui_skips_full_rerender_when_poll_payload_is_visibly_unchanged(self) -> None:
        html = self.main_html()
        self.assertIn("lastRenderSignature", html)
        self.assertIn("function buildRenderSignature(statusPayload, storePayload)", html)
        self.assertIn('delete statusClone.timestamp;', html)
        self.assertIn("if (nextSignature === state.lastRenderSignature) {", html)
        self.assertIn("state.lastRenderSignature = nextSignature;", html)

    def test_main_gui_has_single_runtime_language(self) -> None:
        html = self.main_html()
        self.assertNotIn('id="runtime-mode-store"', html)
        self.assertNotIn('id="clash-candidate"', html)
        self.assertNotIn("Резерва нет", html)
        self.assertNotIn("Bundle стартует только из активного узла.", html)
        self.assertIn("Подписка:", html)
        self.assertIn("Узел:", html)
        self.assertIn("Маршрутизация:", html)

    def test_root_route_is_only_gui_entrypoint(self) -> None:
        self.assertEqual(gui_server.ROOT_GUI_PATHS, ["/", "/index.html"])
        self.assertEqual(gui_server.FAVICON_ROUTE, "/assets/subvost-xray-tun-icon.svg")
        self.assertFalse(hasattr(gui_server, "REVIEW_GUI_PATHS"))
        self.assertFalse(hasattr(gui_server, "LEGACY_GUI_PATHS"))

        do_get_source = inspect.getsource(gui_server.Handler.do_GET)
        self.assertIn('if request_path in {"/favicon.ico", FAVICON_ROUTE}:', do_get_source)
        self.assertIn("if request_path in ROOT_GUI_PATHS:", do_get_source)
        self.assertNotIn("REVIEW_GUI_PATHS", do_get_source)
        self.assertNotIn("LEGACY_GUI_PATHS", do_get_source)

        do_post_source = inspect.getsource(gui_server.Handler.do_POST)
        self.assertIn('"/api/app/terminate"', do_post_source)
        self.assertIn('"/api/app/shutdown-gui"', do_post_source)
        self.assertIn('"/api/nodes/ping"', do_post_source)
        self.assertIn('"/api/routing/import"', do_post_source)
        self.assertIn('"/api/routing/toggle"', do_post_source)
        self.assertIn("schedule_server_shutdown(self.server)", do_post_source)

    def test_launcher_reads_gui_version_from_shared_contract_module(self) -> None:
        launcher = (REPO_ROOT / "libexec" / "open-subvost-gui.sh").read_text(encoding="utf-8")
        self.assertIn('CURRENT_GUI_VERSION="$(load_current_gui_version)"', launcher)
        self.assertIn("from gui_contract import GUI_VERSION", launcher)
        self.assertIn("SUBVOST_GUI_LAUNCH_MODE", launcher)
        self.assertIn("embedded_webview.py", launcher)
        self.assertIn("open_embedded_webview", launcher)
        self.assertIn("WEBKIT_DISABLE_COMPOSITING_MODE", launcher)
        self.assertIn("WEBKIT_DISABLE_DMABUF_RENDERER", launcher)
        self.assertIn("WEBKIT_DMABUF_RENDERER_FORCE_SHM", launcher)
        self.assertIn("WEBKIT_WEBGL_DISABLE_GBM", launcher)
        self.assertIn("WEBKIT_SKIA_ENABLE_CPU_RENDERING", launcher)
        self.assertIn("gui_server.py", launcher)
        self.assertIn("BACKEND_PID_FILE", launcher)
        self.assertNotIn("pkexec env", launcher)
        self.assertNotIn("start-gui-backend-root.sh", launcher)
        self.assertNotIn('CURRENT_GUI_VERSION="2026-', launcher)

    def test_desktop_launcher_does_not_force_backend_restart(self) -> None:
        desktop_entry = (REPO_ROOT / "subvost-xray-tun.desktop").read_text(encoding="utf-8")
        menu_installer = (REPO_ROOT / "libexec" / "install-subvost-gui-menu-entry.sh").read_text(encoding="utf-8")
        common_shell = (REPO_ROOT / "lib" / "subvost-common.sh").read_text(encoding="utf-8")
        expected_icon_name = "subvost-xray-tun-icon"

        self.assertIn("open-subvost-gui.sh", desktop_entry)
        self.assertIn(f"Icon={expected_icon_name}", desktop_entry)
        self.assertNotIn("/assets/subvost-xray-tun-icon.svg", desktop_entry)
        self.assertIn("SUBVOST_GUI_LAUNCH_MODE", desktop_entry)
        self.assertIn("'browser'", desktop_entry)
        self.assertIn('ICON_NAME="${SUBVOST_DESKTOP_ICON_NAME}"', menu_installer)
        self.assertIn("Icon=${ICON_NAME}", menu_installer)
        self.assertIn("subvost_sync_desktop_launcher_icon", menu_installer)
        self.assertIn("SUBVOST_GUI_LAUNCH_MODE", menu_installer)
        self.assertIn("'browser'", menu_installer)
        self.assertIn('SUBVOST_DESKTOP_ICON_NAME="subvost-xray-tun-icon"', common_shell)
        self.assertIn('ln -sfn -- "$icon_path" "$icon_link_path"', common_shell)
        self.assertNotIn("--force-restart-backend", desktop_entry)
        self.assertNotIn("--force-restart-backend", menu_installer)

    def test_install_on_new_pc_selects_pkexec_package_with_policykit_fallback(self) -> None:
        installer = (REPO_ROOT / "libexec" / "install-on-new-pc.sh").read_text(encoding="utf-8")

        self.assertIn("collect_pkexec_dependency_package()", installer)
        self.assertIn('apt_package_exists "pkexec"', installer)
        self.assertIn('apt_package_exists "policykit-1"', installer)
        self.assertIn('PKEXEC_PACKAGE="$(collect_pkexec_dependency_package)"', installer)
        self.assertIn('"$PKEXEC_PACKAGE"', installer)
        self.assertNotIn("apt-get install -y ca-certificates curl iproute2 pkexec", installer)

    def test_stop_button_is_not_disabled_by_stopped_runtime_state(self) -> None:
        html = self.main_html()
        self.assertIn("const stopAllowed = Boolean(state.statusPayload?.runtime?.stop_allowed ?? true);", html)
        self.assertIn("els.stopButton.disabled = state.busy || !stopAllowed;", html)
        self.assertNotIn('els.stopButton.disabled = state.busy || summaryState === "stopped";', html)

    def test_start_button_is_not_disabled_by_runtime_readiness_flag(self) -> None:
        html = self.main_html()
        self.assertIn("const startBlocked = Boolean(state.statusPayload?.runtime?.start_blocked);", html)
        self.assertIn('els.startButton.disabled = state.busy || summaryState === "running" || startBlocked;', html)
        self.assertNotIn('els.startButton.disabled = state.busy || summaryState === "running" || !startReady;', html)

    def test_start_button_shows_readiness_reason_without_hard_disable(self) -> None:
        html = self.main_html()
        self.assertIn('const nextStartReason = state.statusPayload?.runtime?.next_start_reason || "";', html)
        self.assertIn('els.startButton.title = !state.busy && (startBlocked || (summaryState !== "running" && !startReady)) ? nextStartReason : "";', html)
        self.assertIn('setDataAttrIfChanged(els.startButton, "ready", startReady ? "true" : "false");', html)

    def test_main_gui_topbar_keeps_two_columns_at_1280_and_stacks_only_below_1120(self) -> None:
        html = self.main_html()
        self.assertNotIn("@media (max-width: 1280px) {\n      .topbar {", html)
        self.assertIn("@media (max-width: 1120px)", html)
        self.assertIn("grid-template-columns: minmax(0, 1fr) minmax(288px, 360px);", html)
        self.assertIn(".app-shell {\n        grid-template-columns: 1fr;", html)
        self.assertIn(".sidebar-menu,\n      .sidebar-context {\n        grid-template-columns: repeat(3, minmax(0, 1fr));", html)
        self.assertIn(".topbar {\n        grid-template-columns: 1fr;", html)
        self.assertIn("@media (max-width: 920px)", html)
        self.assertIn(".sidebar-menu,\n      .sidebar-context,\n      .workspace {\n        grid-template-columns: 1fr;", html)

    def test_user_backend_shell_action_uses_pkexec_not_sudo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            script = root / "run-xray-tun-subvost.sh"
            script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="ok\n",
                stderr="",
            )

            with (
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "REAL_USER", "tester"),
                patch.object(gui_server, "REAL_HOME", real_home),
                patch.object(gui_server, "APP_PATHS", paths),
                patch("gui_server.os.geteuid", return_value=1000),
                patch("gui_server.subprocess.run", return_value=completed) as run_mock,
            ):
                result = gui_server.run_shell_action("Старт", script, {"ENABLE_FILE_LOGS": "1"})

            self.assertTrue(result.ok)
            command = run_mock.call_args.args[0]
            self.assertEqual(command[:2], ["pkexec", "env"])
            self.assertIn("SUDO_USER=tester", command)
            self.assertIn(f"HOME={real_home}", command)
            self.assertIn(f"SUBVOST_PROJECT_ROOT={root}", command)
            self.assertIn("ENABLE_FILE_LOGS=1", command)
            self.assertIn("/usr/bin/env", command)
            self.assertIn("bash", command)
            self.assertEqual(command[-1], str(script))
            self.assertNotIn("sudo", command)

    def test_cleanup_backend_pid_file_removes_only_matching_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pid_file = Path(temp_dir) / "gui.pid"
            pid_file.write_text("12345", encoding="utf-8")

            removed = gui_server.cleanup_backend_pid_file(pid_file, expected_pid=12345)

            self.assertTrue(removed)
            self.assertFalse(pid_file.exists())

    def test_cleanup_backend_pid_file_keeps_foreign_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pid_file = Path(temp_dir) / "gui.pid"
            pid_file.write_text("12345", encoding="utf-8")

            removed = gui_server.cleanup_backend_pid_file(pid_file, expected_pid=54321)

            self.assertFalse(removed)
            self.assertTrue(pid_file.exists())

    def test_classify_runtime_ownership_matches_current_bundle(self) -> None:
        ownership = gui_server.classify_runtime_ownership({"BUNDLE_PROJECT_ROOT": str(gui_server.PROJECT_ROOT)})

        self.assertEqual(ownership, "current")

    def test_classify_runtime_ownership_detects_foreign_bundle(self) -> None:
        ownership = gui_server.classify_runtime_ownership({"BUNDLE_PROJECT_ROOT": "/tmp/foreign-subvost-bundle"})

        self.assertEqual(ownership, "foreign")

    def test_runtime_stop_required_ignores_foreign_runtime_state(self) -> None:
        state = {
            "XRAY_PID": "12345",
            "TUN_INTERFACE": "tun0",
            "BUNDLE_PROJECT_ROOT": "/tmp/foreign-subvost-bundle",
        }

        with patch("gui_server.is_pid_alive", return_value=True):
            stop_needed = gui_server.runtime_stop_required(state)

        self.assertFalse(stop_needed)

    def test_handle_app_terminate_skips_stop_when_runtime_is_already_down(self) -> None:
        runtime_info = {
            "has_state": False,
            "ownership": "unknown",
            "ownership_label": "Источник не подтверждён",
            "state_bundle_project_root": None,
            "tun_interface": "tun0",
            "xray_pid": None,
            "xray_alive": False,
            "tun_present": False,
            "stack_is_live": False,
            "owned_stack_is_live": False,
        }

        with (
            patch("gui_server.inspect_runtime_state", return_value=runtime_info),
            patch("gui_server.remember_action") as remember_mock,
            patch("gui_server.collect_status", return_value={"summary": {"state": "stopped"}}),
        ):
            payload = gui_server.handle_app_terminate({"source": "window-close"})

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["vpn_stop_requested"])
        self.assertIn("уже не активен", payload["message"])
        remember_mock.assert_called_once()

    def test_handle_app_terminate_stops_runtime_when_it_is_live(self) -> None:
        result = gui_server.CommandResult(name="Закрытие приложения", ok=True, returncode=0, output="stopped")
        runtime_info = {
            "has_state": True,
            "ownership": "current",
            "ownership_label": "Текущий bundle",
            "state_bundle_project_root": str(gui_server.PROJECT_ROOT),
            "tun_interface": "tun0",
            "xray_pid": "12345",
            "xray_alive": True,
            "tun_present": True,
            "stack_is_live": True,
            "owned_stack_is_live": True,
        }

        with (
            patch("gui_server.inspect_runtime_state", return_value=runtime_info),
            patch("gui_server.run_shell_action", return_value=result) as run_mock,
            patch("gui_server.remember_action") as remember_mock,
            patch("gui_server.collect_status", return_value={"summary": {"state": "stopped"}}),
        ):
            payload = gui_server.handle_app_terminate({"source": "window-close"})

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["vpn_stop_requested"])
        self.assertIn("VPN runtime остановлен", payload["message"])
        run_mock.assert_called_once_with("Закрытие приложения", gui_server.STOP_SCRIPT)
        remember_mock.assert_called_once()

    def test_handle_app_terminate_does_not_stop_foreign_runtime(self) -> None:
        runtime_info = {
            "has_state": True,
            "ownership": "foreign",
            "ownership_label": "Другой bundle",
            "state_bundle_project_root": "/tmp/foreign-subvost-bundle",
            "tun_interface": "tun0",
            "xray_pid": "12345",
            "xray_alive": True,
            "tun_present": True,
            "stack_is_live": True,
            "owned_stack_is_live": False,
        }

        with (
            patch("gui_server.inspect_runtime_state", return_value=runtime_info),
            patch("gui_server.run_shell_action") as run_mock,
            patch("gui_server.remember_action") as remember_mock,
            patch("gui_server.collect_status", return_value={"summary": {"state": "degraded"}}),
        ):
            payload = gui_server.handle_app_terminate({"source": "window-close"})

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["vpn_stop_requested"])
        self.assertIn("другого bundle", payload["message"])
        run_mock.assert_not_called()
        remember_mock.assert_called_once()

    def test_handle_gui_shutdown_does_not_stop_runtime(self) -> None:
        with (
            patch("gui_server.inspect_runtime_state") as inspect_mock,
            patch("gui_server.run_shell_action") as run_mock,
            patch("gui_server.remember_action") as remember_mock,
            patch("gui_server.collect_status", return_value={"summary": {"state": "running"}}),
        ):
            payload = gui_server.handle_gui_shutdown({"source": "window-close"})

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["vpn_stop_requested"])
        self.assertIn("без остановки VPN", payload["message"])
        inspect_mock.assert_not_called()
        run_mock.assert_not_called()
        remember_mock.assert_called_once()

    def test_handle_stop_rejects_foreign_runtime(self) -> None:
        runtime_info = {
            "has_state": True,
            "ownership": "foreign",
            "ownership_label": "Другой bundle",
            "state_bundle_project_root": "/tmp/foreign-subvost-bundle",
            "tun_interface": "tun0",
            "xray_pid": "12345",
            "xray_alive": True,
            "tun_present": True,
            "stack_is_live": True,
            "owned_stack_is_live": False,
        }

        with patch("gui_server.inspect_runtime_state", return_value=runtime_info):
            with self.assertRaisesRegex(ValueError, "другого bundle"):
                gui_server.handle_stop()

    def test_handle_start_rejects_foreign_runtime_before_store_checks(self) -> None:
        runtime_info = {
            "has_state": True,
            "ownership": "foreign",
            "ownership_label": "Другой bundle",
            "state_bundle_project_root": "/tmp/foreign-subvost-bundle",
            "tun_interface": "tun0",
            "xray_pid": None,
            "xray_alive": False,
            "tun_present": False,
            "stack_is_live": False,
            "owned_stack_is_live": False,
        }

        with patch("gui_server.inspect_runtime_state", return_value=runtime_info):
            with self.assertRaisesRegex(ValueError, "другого bundle"):
                gui_server.handle_start()

    def test_runtime_scripts_persist_and_guard_bundle_project_root(self) -> None:
        run_script = (REPO_ROOT / "libexec" / "run-xray-tun-subvost.sh").read_text(encoding="utf-8")
        stop_script = (REPO_ROOT / "libexec" / "stop-xray-tun-subvost.sh").read_text(encoding="utf-8")

        self.assertIn("BUNDLE_PROJECT_ROOT", run_script)
        self.assertIn("printf 'BUNDLE_PROJECT_ROOT=%s\\n' \"$SUBVOST_PROJECT_ROOT\" >>\"$STATE_FILE\"", run_script)
        self.assertIn("read_state_bundle_project_root()", run_script)
        self.assertIn("STATE_BUNDLE_PROJECT_ROOT", stop_script)
        self.assertIn("Файл состояния принадлежит другому bundle", stop_script)
        self.assertIn("не будет останавливать неподтверждённый runtime", stop_script)

    def test_root_backend_shell_action_runs_script_directly(self) -> None:
        script = Path("/tmp/run-xray-tun-subvost.sh")
        with patch("gui_server.os.geteuid", return_value=0):
            command = gui_server.build_shell_action_command(script, {"SUDO_USER": "tester"})

        self.assertEqual(command, [str(script)])

    def test_resolve_active_xray_config_prefers_snapshot_only_for_live_stack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            template = root / "xray-tun-subvost.json"
            template.write_text("{}", encoding="utf-8")
            paths.generated_xray_config_file.write_text('{"generated": true}', encoding="utf-8")
            paths.active_runtime_xray_config_file.write_text('{"snapshot": true}', encoding="utf-8")

            store = {"active_selection": {"profile_id": "profile-1", "node_id": "node-1"}}
            state = {"XRAY_CONFIG": str(paths.active_runtime_xray_config_file)}

            with patch.object(gui_server, "APP_PATHS", paths), patch.object(gui_server, "XRAY_TEMPLATE_PATH", template):
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path(store, state, stack_is_live=True),
                    paths.active_runtime_xray_config_file,
                )
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path(store, state, stack_is_live=False),
                    paths.generated_xray_config_file,
                )

    def test_resolve_active_xray_config_returns_generated_path_when_stack_is_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            paths.generated_xray_config_file.write_text('{"generated": true}', encoding="utf-8")
            with patch.object(gui_server, "APP_PATHS", paths):
                self.assertEqual(
                    gui_server.resolve_active_xray_config_path({}, {}, stack_is_live=False),
                    paths.generated_xray_config_file,
                )

    def test_resolve_active_xray_config_points_to_generated_path_without_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            paths.store_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(gui_server, "APP_PATHS", paths):
                resolved = gui_server.resolve_active_xray_config_path(
                    {"active_selection": {"profile_id": None, "node_id": None}},
                    {"XRAY_CONFIG": str(paths.active_runtime_xray_config_file)},
                    stack_is_live=False,
                )
                self.assertEqual(resolved, paths.generated_xray_config_file)

    def test_describe_stack_status_for_running_runtime(self) -> None:
        status = gui_server.describe_stack_status(
            xray_alive=True,
            tun_present=True,
            tun_interface="tun0",
            ownership="current",
        )
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["stack_line"], "Xray core")
        self.assertIn("Единый TUN-runtime", status["stack_subline"])
        self.assertIn("tun0", status["description"])

    def test_describe_stack_status_for_degraded_runtime(self) -> None:
        status = gui_server.describe_stack_status(
            xray_alive=True,
            tun_present=False,
            tun_interface="tun0",
            ownership="current",
        )
        self.assertEqual(status["state"], "degraded")
        self.assertEqual(status["stack_line"], "Xray core")
        self.assertIn("Часть runtime активна", status["description"])

    def test_describe_stack_status_for_foreign_runtime(self) -> None:
        status = gui_server.describe_stack_status(
            xray_alive=True,
            tun_present=True,
            tun_interface="tun0",
            ownership="foreign",
        )
        self.assertEqual(status["state"], "degraded")
        self.assertIn("другой bundle", status["label"])
        self.assertIn("управление заблокировано", status["stack_subline"])

    def test_normalize_iso_timestamp_preserves_valid_values(self) -> None:
        self.assertEqual(
            gui_server.normalize_iso_timestamp("2026-04-05T10:11:12+02:00"),
            "2026-04-05T10:11:12+02:00",
        )
        self.assertEqual(
            gui_server.normalize_iso_timestamp("2026-04-05T08:11:12Z"),
            "2026-04-05T08:11:12+00:00",
        )
        self.assertIsNone(gui_server.normalize_iso_timestamp("not-a-date"))

    def test_collect_traffic_metrics_computes_rates_from_interface_counters(self) -> None:
        previous_sample = gui_server.LAST_TRAFFIC_SAMPLE.copy()
        gui_server.LAST_TRAFFIC_SAMPLE.update({"interface": None, "timestamp": None, "rx_bytes": None, "tx_bytes": None})
        try:
            with (
                patch.object(gui_server, "read_interface_byte_counter", side_effect=[1000, 2000, 1600, 2600]),
                patch("gui_server.time.monotonic", side_effect=[10.0, 12.0]),
            ):
                first = gui_server.collect_traffic_metrics("tun0")
                second = gui_server.collect_traffic_metrics("tun0")
        finally:
            gui_server.LAST_TRAFFIC_SAMPLE.update(previous_sample)

        self.assertTrue(first["available"])
        self.assertEqual(first["rx_bytes"], 1000)
        self.assertEqual(first["tx_bytes"], 2000)
        self.assertEqual(first["rx_rate_bytes_per_sec"], 0.0)
        self.assertEqual(first["tx_rate_bytes_per_sec"], 0.0)
        self.assertEqual(second["rx_rate_bytes_per_sec"], 300.0)
        self.assertEqual(second["tx_rate_bytes_per_sec"], 300.0)
        self.assertEqual(second["rx_rate_label"], "300 B/s")

    def test_handle_node_ping_returns_latency_and_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")

            store = ensure_store_initialized(paths, root)
            manual_profile = next(profile for profile in store["profiles"] if profile["id"] == "manual")
            manual_profile["nodes"].append(
                {
                    "id": "node-1",
                    "fingerprint": "fingerprint-1",
                    "name": "Node-1",
                    "protocol": "vless",
                    "raw_uri": "vless://...",
                    "origin": {"kind": "manual", "subscription_id": None},
                    "enabled": True,
                    "user_renamed": False,
                    "parse_error": "",
                    "normalized": {"address": "example.com", "port": 443, "protocol": "vless"},
                    "created_at": "2026-04-04T00:00:00",
                    "updated_at": "2026-04-04T00:00:00",
                }
            )
            save_store(paths, store)

            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "XRAY_TEMPLATE_PATH", template),
                patch.object(gui_server, "ping_node", return_value={"host": "example.com", "port": 443, "latency_ms": 42.5, "label": "42.5 мс", "timestamp": "2026-04-04T10:00:00", "ok": True}),
            ):
                gui_server.PING_CACHE.clear()
                response = gui_server.handle_node_ping({"profile_id": "manual", "node_id": "node-1"})

            self.assertTrue(response["ok"])
            self.assertEqual(response["ping"]["latency_ms"], 42.5)
            self.assertEqual(response["ping"]["label"], "42.5 мс")
            cache = response["status"]["ping"]["cache"]
            self.assertIn("manual:node-1", cache)
            self.assertEqual(cache["manual:node-1"]["latency_ms"], 42.5)


class GuiServerSubscriptionRollbackTests(unittest.TestCase):
    def test_handle_subscription_refresh_persists_last_error_without_switching_runtime_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")

            store = ensure_store_initialized(paths, root)
            subscription = add_subscription(store, "Test", "https://example.com/sub")
            valid_payload = b"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Stable\n"
            with patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(valid_payload, {"ETag": "etag-1"})):
                refresh_subscription(store, subscription["id"])
            save_store(paths, store)

            invalid_payload = base64.urlsafe_b64encode(
                (
                    "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Changed\n"
                    "vless://broken\n"
                ).encode("utf-8")
            )
            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "XRAY_TEMPLATE_PATH", template),
                patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(invalid_payload, {"ETag": "etag-2"})),
            ):
                with self.assertRaisesRegex(ValueError, "Сохранена предыдущая версия"):
                    gui_server.handle_subscription_refresh({"subscription_id": subscription["id"]})

            persisted = json.loads(paths.store_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["subscriptions"][0]["last_status"], "error")
            self.assertIn("невалидных строк 1", persisted["subscriptions"][0]["last_error"])
            self.assertEqual(len(persisted["profiles"][1]["nodes"]), 1)
            self.assertIn("#Stable", persisted["profiles"][1]["nodes"][0]["raw_uri"])

    def test_handle_subscription_add_rolls_back_failed_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            ensure_store_initialized(paths, root)

            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch.object(gui_server, "XRAY_TEMPLATE_PATH", template),
                patch("subvost_store.urllib.request.urlopen", return_value=FakeResponse(b"bad-link\n")),
            ):
                with self.assertRaisesRegex(ValueError, "Подписка не добавлена"):
                    gui_server.handle_subscription_add({"name": "Broken", "url": "https://example.com/sub"})

            persisted = json.loads(paths.store_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["subscriptions"], [])
            self.assertEqual(len(persisted["profiles"]), 1)

    def test_handle_start_requires_active_node(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            ensure_store_initialized(paths, root)

            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch(
                    "gui_server.inspect_runtime_state",
                    return_value={
                        "has_state": False,
                        "ownership": "unknown",
                        "ownership_label": "Источник не подтверждён",
                        "state_bundle_project_root": None,
                        "tun_interface": "tun0",
                        "xray_pid": None,
                        "xray_alive": False,
                        "tun_present": False,
                        "stack_is_live": False,
                        "owned_stack_is_live": False,
                    },
                ),
            ):
                with self.assertRaisesRegex(ValueError, "сначала выбери и активируй валидный узел"):
                    gui_server.handle_start()

    def test_handle_start_rejects_not_ready_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            paths = build_app_paths(real_home, str(real_home / ".config"))
            template = root / "xray-tun-subvost.json"
            template.write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            store = ensure_store_initialized(paths, root)
            store["routing"]["profiles"].append(
                {
                    "id": "routing-1",
                    "name": "SubVostVPN",
                    "name_key": "subvostvpn",
                    "enabled": True,
                    "source_format": "json",
                    "raw_payload": {"name": "SubVostVPN"},
                    "global_proxy": True,
                    "domain_strategy": "AsIs",
                    "geoip_url": "https://example.com/geoip.dat",
                    "geosite_url": "https://example.com/geosite.dat",
                    "direct_sites": [],
                    "direct_ip": [],
                    "proxy_sites": [],
                    "proxy_ip": [],
                    "block_sites": [],
                    "block_ip": [],
                    "dns_hosts": {},
                    "domestic_dns_domain": "",
                    "domestic_dns_ip": "",
                    "domestic_dns_type": "",
                    "remote_dns_domain": "",
                    "remote_dns_ip": "",
                    "remote_dns_type": "",
                    "fake_dns": False,
                    "route_order": ["block", "direct", "proxy"],
                    "last_updated": "",
                    "supported_entry_count": 0,
                    "stored_only_fields": [],
                    "ignored_fields": [],
                    "unknown_fields": [],
                    "created_at": "2026-04-08T00:00:00+00:00",
                    "updated_at": "2026-04-08T00:00:00+00:00",
                }
            )
            store["routing"]["active_profile_id"] = "routing-1"
            store["routing"]["enabled"] = True
            store["routing"]["runtime_ready"] = False
            store["routing"]["runtime_error"] = "geodata отсутствует"
            save_store(paths, store)

            with (
                patch.object(gui_server, "APP_PATHS", paths),
                patch.object(gui_server, "PROJECT_ROOT", root),
                patch(
                    "gui_server.inspect_runtime_state",
                    return_value={
                        "has_state": False,
                        "ownership": "unknown",
                        "ownership_label": "Источник не подтверждён",
                        "state_bundle_project_root": None,
                        "tun_interface": "tun0",
                        "xray_pid": None,
                        "xray_alive": False,
                        "tun_present": False,
                        "stack_is_live": False,
                        "owned_stack_is_live": False,
                    },
                ),
            ):
                with self.assertRaisesRegex(ValueError, "geodata|маршрутизации"):
                    gui_server.handle_start()


if __name__ == "__main__":
    unittest.main()
