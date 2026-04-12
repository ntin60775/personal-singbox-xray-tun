from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from subvost_app_service import (  # noqa: E402
    CommandResult,
    ServiceContext,
    ServiceState,
    SubvostAppService,
)
from subvost_paths import build_app_paths  # noqa: E402
from subvost_store import ensure_store_initialized  # noqa: E402


class SubvostAppServiceTests(unittest.TestCase):
    def make_service(self, root: Path, real_home: Path) -> SubvostAppService:
        app_paths = build_app_paths(real_home, str(real_home / ".config"))
        context = ServiceContext(
            project_root=root,
            real_user="tester",
            real_home=real_home,
            real_uid=1000,
            real_gid=1000,
            app_paths=app_paths,
            state_file=real_home / ".xray-tun-subvost.state",
            resolv_backup=real_home / ".xray-tun-subvost.resolv.conf.backup",
            log_dir=root / "logs",
            run_script=root / "run-xray-tun-subvost.sh",
            stop_script=root / "stop-xray-tun-subvost.sh",
            diag_script=root / "capture-xray-tun-state.sh",
            xray_template_path=root / "xray-tun-subvost.json",
        )
        return SubvostAppService(context=context, state=ServiceState())

    def test_start_runtime_rejects_foreign_runtime_before_store_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            runtime_info = {
                "has_state": True,
                "ownership": "foreign",
                "ownership_label": "Другой экземпляр",
                "state_bundle_project_root": "/tmp/foreign-subvost-bundle",
                "tun_interface": "tun0",
                "xray_pid": None,
                "xray_alive": False,
                "tun_present": False,
                "stack_is_live": False,
                "owned_stack_is_live": False,
            }

            with patch.object(service, "inspect_runtime_state", return_value=runtime_info):
                with self.assertRaisesRegex(ValueError, "другого экземпляра"):
                    service.start_runtime()

    def test_collect_store_snapshot_returns_store_and_status_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            with patch.object(service, "collect_status", return_value={"summary": {"state": "stopped"}}):
                payload = service.collect_store_snapshot()

            self.assertTrue(payload["ok"])
            self.assertIn("store", payload)
            self.assertEqual(payload["status"]["summary"]["state"], "stopped")
            self.assertEqual(payload["store"]["summary"]["subscriptions_total"], 0)

    def test_add_subscription_rolls_back_store_when_initial_refresh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            with patch("subvost_app_service.store_refresh_subscription", side_effect=ValueError("network down")):
                with self.assertRaisesRegex(ValueError, "Подписка не добавлена"):
                    service.add_subscription("", "https://example.com/subscription")

            store = ensure_store_initialized(service.context.app_paths, root)
            self.assertEqual(store["subscriptions"], [])

    def test_add_subscription_returns_store_response_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            refresh_result = {
                "status": "ok",
                "valid": 1,
                "invalid": 0,
                "unique_nodes": 1,
                "duplicate_lines": 0,
            }
            with (
                patch("subvost_app_service.store_refresh_subscription", return_value=refresh_result),
                patch.object(service, "collect_status", return_value={"summary": {"state": "stopped"}}),
            ):
                payload = service.add_subscription("", "https://example.com/subscription")

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"]["summary"]["state"], "stopped")
            self.assertEqual(payload["refresh"], refresh_result)
            self.assertEqual(payload["subscription"]["url"], "https://example.com/subscription")
            self.assertEqual(payload["store"]["summary"]["subscriptions_total"], 1)

    def test_capture_diagnostics_remembers_path_from_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            with (
                patch.object(
                    service,
                    "run_shell_action",
                    return_value=CommandResult(
                        name="Диагностика",
                        ok=True,
                        returncode=0,
                        output="dump saved to /tmp/xray-tun-state-2026-04-09.log",
                    ),
                ),
                patch.object(service, "collect_status", return_value={"summary": {"state": "stopped"}}),
            ):
                payload = service.capture_diagnostics()

            self.assertEqual(payload["summary"]["state"], "stopped")
            self.assertIn("/tmp/xray-tun-state-2026-04-09.log", service.state.last_action["message"])
            self.assertEqual(service.state.last_action["name"], "Диагностика")

    def test_shutdown_gui_returns_status_without_runtime_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)

            with patch.object(service, "collect_status", return_value={"summary": {"state": "running"}}):
                payload = service.shutdown_gui("window-close")

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["vpn_stop_requested"])
            self.assertEqual(payload["status"]["summary"]["state"], "running")
            self.assertIn("без остановки VPN-подключения", payload["message"])

    def test_collect_status_reports_transport_and_security_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            template = {
                "outbounds": [
                    {
                        "tag": "proxy",
                        "protocol": "vless",
                        "settings": {
                            "vnext": [
                                {
                                    "address": "edge.example.com",
                                    "port": 443,
                                }
                            ]
                        },
                        "streamSettings": {
                            "network": "grpc",
                            "security": "reality",
                            "realitySettings": {
                                "serverName": "cdn.example.com",
                            },
                        },
                    }
                ],
                "inbounds": [
                    {
                        "tag": "socks-in",
                        "listen": "127.0.0.1",
                        "port": 10808,
                    }
                ],
                "dns": {
                    "servers": ["1.1.1.1", "8.8.8.8"],
                },
            }
            (root / "xray-tun-subvost.json").write_text(json.dumps(template), encoding="utf-8")
            service = self.make_service(root, real_home)
            store = ensure_store_initialized(service.context.app_paths, root)
            manual_profile = next(profile for profile in store["profiles"] if profile["id"] == "manual")
            manual_profile["nodes"].append(
                {
                    "id": "node-1",
                    "fingerprint": "fingerprint-1",
                    "name": "Edge",
                    "protocol": "vless",
                    "raw_uri": "vless://...",
                    "origin": {"kind": "manual", "subscription_id": None},
                    "enabled": True,
                    "user_renamed": False,
                    "parse_error": "",
                    "normalized": {
                        "address": "edge.example.com",
                        "port": 443,
                        "protocol": "vless",
                        "network": "grpc",
                        "security": "reality",
                        "service_name": "grpc-service",
                        "server_name": "cdn.example.com",
                        "sni": "cdn.example.com",
                    },
                    "created_at": "2026-04-09T00:00:00",
                    "updated_at": "2026-04-09T00:00:00",
                }
            )
            store["active_selection"]["profile_id"] = "manual"
            store["active_selection"]["node_id"] = "node-1"
            service.persist_store(store)

            state = {
                "TUN_INTERFACE": "tun0",
                "XRAY_CONFIG_SOURCE": "store",
                "XRAY_CONFIG": str(service.context.app_paths.generated_xray_config_file),
                "BUNDLE_PROJECT_ROOT": str(root),
            }
            runtime_info = {
                "state": state,
                "has_state": True,
                "ownership": "current",
                "ownership_label": "Текущий экземпляр",
                "state_bundle_project_root": str(root),
                "tun_interface": "tun0",
                "xray_pid": None,
                "xray_alive": False,
                "tun_present": False,
                "stack_is_live": False,
                "owned_stack_is_live": False,
            }

            with (
                patch.object(service, "load_state_file", return_value=state),
                patch.object(service, "inspect_runtime_state", return_value=runtime_info),
                patch.object(service, "read_resolv_conf_nameservers", return_value=["1.1.1.1", "8.8.8.8"]),
                patch.object(service, "read_interface_addresses", return_value="10.0.0.2/30"),
            ):
                payload = service.collect_status()

            self.assertEqual(payload["connection"]["transport_label"], "GRPC")
            self.assertEqual(payload["connection"]["security_label"], "REALITY")
            self.assertEqual(payload["connection"]["remote_sni"], "cdn.example.com")

    def test_collect_status_keeps_connected_since_for_foreign_live_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            template = {
                "outbounds": [{"tag": "proxy"}],
                "inbounds": [],
                "dns": {"servers": []},
            }
            (root / "xray-tun-subvost.json").write_text(json.dumps(template), encoding="utf-8")
            service = self.make_service(root, real_home)

            state = {
                "STARTED_AT": "2026-04-12T13:14:15+02:00",
                "TUN_INTERFACE": "tun0",
                "XRAY_CONFIG_SOURCE": "store",
                "BUNDLE_PROJECT_ROOT": "/tmp/foreign-subvost-bundle",
            }
            runtime_info = {
                "state": state,
                "has_state": True,
                "ownership": "foreign",
                "ownership_label": "Другой экземпляр",
                "state_bundle_project_root": "/tmp/foreign-subvost-bundle",
                "tun_interface": "tun0",
                "xray_pid": "1234",
                "xray_alive": True,
                "tun_present": True,
                "stack_is_live": True,
                "owned_stack_is_live": False,
            }

            with (
                patch.object(service, "load_state_file", return_value=state),
                patch.object(service, "inspect_runtime_state", return_value=runtime_info),
                patch.object(service, "read_resolv_conf_nameservers", return_value=["192.168.100.1"]),
                patch.object(service, "collect_traffic_metrics", return_value={"rx_rate_label": "0 B/s", "tx_rate_label": "0 B/s"}),
                patch.object(service, "collect_log_payload", return_value={}),
                patch.object(service, "find_latest_diagnostic", return_value=None),
                patch.object(service, "read_interface_addresses", return_value="10.0.0.2/30"),
            ):
                payload = service.collect_status()

            self.assertEqual(payload["runtime"]["ownership"], "foreign")
            self.assertEqual(payload["runtime"]["connected_since"], "2026-04-12T13:14:15+02:00")

    def test_ping_node_by_id_updates_cache_and_returns_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_home = root / "home"
            real_home.mkdir()
            (root / "xray-tun-subvost.json").write_text(json.dumps({"outbounds": [{"tag": "proxy"}]}), encoding="utf-8")
            service = self.make_service(root, real_home)
            store = ensure_store_initialized(service.context.app_paths, root)
            manual_profile = next(profile for profile in store["profiles"] if profile["id"] == "manual")
            manual_profile["nodes"].append(
                {
                    "id": "node-1",
                    "fingerprint": "fingerprint-1",
                    "name": "Edge",
                    "protocol": "vless",
                    "raw_uri": "vless://...",
                    "origin": {"kind": "manual", "subscription_id": None},
                    "enabled": True,
                    "user_renamed": False,
                    "parse_error": "",
                    "normalized": {
                        "address": "edge.example.com",
                        "port": 443,
                    },
                    "created_at": "2026-04-09T00:00:00",
                    "updated_at": "2026-04-09T00:00:00",
                }
            )
            service.persist_store(store)

            with (
                patch.object(service, "ping_node", return_value={"label": "12.4 мс", "ok": True, "host": "edge.example.com", "port": 443, "latency_ms": 12.4, "timestamp": "2026-04-09T10:00:00"}),
                patch.object(service, "collect_status", return_value={"summary": {"state": "running"}}),
            ):
                payload = service.ping_node_by_id("manual", "node-1")

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"]["summary"]["state"], "running")
            self.assertEqual(payload["ping"]["node_id"], "node-1")
            self.assertIn("manual:node-1", service.state.ping_cache)


if __name__ == "__main__":
    unittest.main()
