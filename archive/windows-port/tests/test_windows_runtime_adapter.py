from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from windows_runtime_adapter import (  # noqa: E402
    WINDOWS_TUN_ADAPTER,
    CommandResult,
    WindowsRuntimeController,
    decode_command_output,
    parse_ipv4_default_gateway,
    prepare_windows_xray_config,
)


ROUTE_PRINT = """
IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.50     25
===========================================================================
"""


def active_config() -> dict[str, object]:
    return {
        "inbounds": [
            {"tag": "tun-in", "protocol": "tun", "settings": {"name": "tun0", "mtu": 1500}},
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {"vnext": [{"address": "edge.example.com", "port": 443, "users": []}]},
                "streamSettings": {"network": "tcp", "sockopt": {"interface": "eth0", "mark": 8421}},
            },
            {"tag": "direct", "protocol": "freedom", "streamSettings": {"sockopt": {"interface": "eth0", "mark": 8421}}},
        ],
    }


class FakeProcess:
    pid = 4242

    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True


class FakeRunner:
    def __init__(self, *, adapter_ok: bool = True) -> None:
        self.adapter_ok = adapter_ok
        self.commands: list[list[str]] = []

    def run(self, args, *, cwd=None, timeout=20):  # noqa: ANN001
        command = [str(item) for item in args]
        self.commands.append(command)
        if command[:2] == ["route", "print"]:
            return CommandResult(command, 0, ROUTE_PRINT, "")
        if command[:2] == ["route", "ADD"]:
            return CommandResult(command, 0, "OK", "")
        if command[:2] == ["route", "DELETE"]:
            return CommandResult(command, 0, "OK", "")
        if command[:3] == ["netsh", "interface", "show"]:
            code = 0 if self.adapter_ok else 1
            return CommandResult(command, code, "SubvostTun", "" if self.adapter_ok else "Не найден интерфейс")
        if command and command[0] in {"taskkill", "ipconfig", "tasklist"}:
            return CommandResult(command, 0, "OK", "")
        return CommandResult(command, 0, "OK", "")


class WindowsRuntimeAdapterTests(unittest.TestCase):
    def make_controller(self, temp_dir: str, *, runner: FakeRunner, process: FakeProcess | None = None) -> WindowsRuntimeController:
        root = Path(temp_dir)
        runtime_dir = root / "runtime"
        state_dir = root / "state"
        runtime_dir.mkdir()
        state_dir.mkdir()
        (runtime_dir / "xray.exe").write_text("fake", encoding="utf-8")
        (runtime_dir / "wintun.dll").write_text("fake", encoding="utf-8")
        config_path = state_dir / "generated-xray-config.json"
        config_path.write_text(json.dumps(active_config()), encoding="utf-8")
        fake_process = process or FakeProcess()
        return WindowsRuntimeController(
            project_root=root,
            config_path=config_path,
            active_config_path=state_dir / "active-runtime-xray-config.json",
            runtime_dir=runtime_dir,
            state_file=state_dir / "windows-runtime-state.json",
            log_dir=state_dir / "logs",
            diagnostic_dir=state_dir / "logs" / "diagnostics",
            runner=runner,
            popen_factory=lambda *args, **kwargs: fake_process,
            resolver=lambda host: ["203.0.113.8"],
            sleep=lambda seconds: None,
        )

    def test_decode_command_output_uses_replacement_instead_of_crashing(self) -> None:
        text = decode_command_output(b"\xff\xfeR\x00")

        self.assertTrue(text)

    def test_parse_ipv4_default_gateway(self) -> None:
        gateway, interface = parse_ipv4_default_gateway(ROUTE_PRINT)

        self.assertEqual(gateway, "192.168.1.1")
        self.assertEqual(interface, "192.168.1.50")

    def test_prepare_windows_xray_config_renames_tun_and_removes_linux_sockopt(self) -> None:
        prepared = prepare_windows_xray_config(active_config())

        self.assertEqual(prepared["inbounds"][0]["settings"]["name"], WINDOWS_TUN_ADAPTER)
        for outbound in prepared["outbounds"]:
            sockopt = outbound.get("streamSettings", {}).get("sockopt", {})
            self.assertNotIn("interface", sockopt)
            self.assertNotIn("mark", sockopt)

    def test_start_adds_host_route_and_writes_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FakeRunner()
            controller = self.make_controller(temp_dir, runner=runner)

            state = controller.start()

            self.assertEqual(state["state"], "running")
            self.assertEqual(state["adapter"], WINDOWS_TUN_ADAPTER)
            self.assertIn(["route", "ADD", "203.0.113.8", "MASK", "255.255.255.255", "192.168.1.1", "METRIC", "1"], runner.commands)
            self.assertTrue(controller.state_file.exists())
            prepared = json.loads(controller.active_config_path.read_text(encoding="utf-8"))
            self.assertEqual(prepared["inbounds"][0]["settings"]["name"], WINDOWS_TUN_ADAPTER)

    def test_start_rolls_back_route_when_adapter_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            process = FakeProcess()
            runner = FakeRunner(adapter_ok=False)
            controller = self.make_controller(temp_dir, runner=runner, process=process)

            with self.assertRaisesRegex(ValueError, "Не найден адаптер"):
                controller.start()

            self.assertTrue(process.terminated)
            self.assertIn(["route", "DELETE", "203.0.113.8", "MASK", "255.255.255.255"], runner.commands)

    def test_stop_deletes_saved_routes_and_kills_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FakeRunner()
            controller = self.make_controller(temp_dir, runner=runner)
            controller.write_state(
                {
                    "state": "running",
                    "xray_pid": 4242,
                    "route_delete_commands": [["route", "DELETE", "203.0.113.8", "MASK", "255.255.255.255"]],
                }
            )

            state = controller.stop()

            self.assertEqual(state["state"], "stopped")
            self.assertIn(["route", "DELETE", "203.0.113.8", "MASK", "255.255.255.255"], runner.commands)
            self.assertIn(["taskkill", "/PID", "4242", "/T", "/F"], runner.commands)

    def test_diagnostics_contains_recovery_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FakeRunner()
            controller = self.make_controller(temp_dir, runner=runner)
            controller.write_state(
                {
                    "state": "running",
                    "xray_pid": 4242,
                    "route_delete_commands": [["route", "DELETE", "203.0.113.8", "MASK", "255.255.255.255"]],
                }
            )

            payload = controller.capture_diagnostics()

            self.assertTrue(Path(payload["path"]).exists())
            self.assertIn("route DELETE 203.0.113.8 MASK 255.255.255.255", payload["diagnostic"]["recovery"]["route_delete_commands"])


if __name__ == "__main__":
    unittest.main()
