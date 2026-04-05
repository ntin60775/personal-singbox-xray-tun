from __future__ import annotations

import base64
import inspect
import json
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
        self.assertEqual(gui_contract.GUI_VERSION, "2026-04-04-subscription-hwid-fix-v1")

    def test_main_gui_html_is_loaded_from_single_asset(self) -> None:
        self.assertEqual(gui_server.INDEX_HTML, self.main_html())
        self.assertIn("function normalizeDataAttrName(name)", gui_server.INDEX_HTML)
        self.assertIn("function setHtmlIfChanged(element, markup, cacheKey = \"\")", gui_server.INDEX_HTML)
        self.assertIn("renderCache", gui_server.INDEX_HTML)
        self.assertIn("setHtmlIfChanged(els.nodeList, markup, \"nodes\")", gui_server.INDEX_HTML)
        self.assertIn('data-${normalizeDataAttrName(key)}="${escapeAttr(value)}"', gui_server.INDEX_HTML)
        self.assertNotIn('data-${key}="${escapeAttr(value)}"', gui_server.INDEX_HTML)

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
        self.assertIn('id="log-list"', html)
        self.assertIn('id="refresh-all-button"', html)
        self.assertIn('id="panel-log"', html)
        self.assertIn('id="panel-subscriptions"', html)
        self.assertIn('id="panel-nodes"', html)
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
        self.assertNotIn('id="sidebar-nav"', html)
        self.assertNotIn('id="profile-list"', html)
        self.assertNotIn('id="logging-toggle"', html)
        self.assertNotIn('id="command-output"', html)
        self.assertNotIn("Активный маршрут", html)
        self.assertNotIn("Состояние стека", html)
        self.assertNotIn("Ручной импорт ссылок", html)

    def test_main_gui_has_single_runtime_language(self) -> None:
        html = self.main_html()
        self.assertNotIn('id="runtime-mode-store"', html)
        self.assertNotIn('id="clash-candidate"', html)
        self.assertNotIn("Резерва нет", html)
        self.assertNotIn("Bundle стартует только из активного узла.", html)
        self.assertIn("Подписка:", html)
        self.assertIn("Узел:", html)

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
        self.assertIn('"/api/nodes/ping"', do_post_source)

    def test_launcher_reads_gui_version_from_shared_contract_module(self) -> None:
        launcher = (REPO_ROOT / "libexec" / "open-subvost-gui.sh").read_text(encoding="utf-8")
        self.assertIn('CURRENT_GUI_VERSION="$(load_current_gui_version)"', launcher)
        self.assertIn("from gui_contract import GUI_VERSION", launcher)
        self.assertIn("SUBVOST_GUI_LAUNCH_MODE", launcher)
        self.assertIn("embedded_webview.py", launcher)
        self.assertIn("open_embedded_webview", launcher)
        self.assertNotIn('CURRENT_GUI_VERSION="2026-', launcher)

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
        )
        self.assertEqual(status["state"], "degraded")
        self.assertEqual(status["stack_line"], "Xray core")
        self.assertIn("Часть runtime активна", status["description"])

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
            ):
                with self.assertRaisesRegex(ValueError, "сначала выбери и активируй валидный узел"):
                    gui_server.handle_start()


if __name__ == "__main__":
    unittest.main()
