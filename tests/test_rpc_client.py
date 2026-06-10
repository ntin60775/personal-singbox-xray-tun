from __future__ import annotations

import os
import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "gui"))

from rpc_client import SubvostRPCClient, RPCError  # noqa: E402

BACKEND_PATH = REPO_ROOT / "subvostd"


@unittest.skipIf(not BACKEND_PATH.exists(), f"subvostd binary not found at {BACKEND_PATH}, build with: make build")
class TestRPCClient(unittest.TestCase):
    def test_rpc_client_status(self) -> None:
        client = SubvostRPCClient([str(BACKEND_PATH), "--mode", "serve"])
        try:
            result = client.call("status")
            self.assertIsInstance(result, dict)
            self.assertIn("active_node", result)
        finally:
            client.shutdown()

    def test_rpc_client_error(self) -> None:
        client = SubvostRPCClient([str(BACKEND_PATH), "--mode", "serve"])
        try:
            with self.assertRaises(RPCError):
                client.call("nonexistent.method")
        finally:
            client.shutdown()

    def test_rpc_client_shutdown(self) -> None:
        client = SubvostRPCClient([str(BACKEND_PATH), "--mode", "serve"])
        client.call("status")  # ensures proc is started
        p = client._proc
        client.shutdown()
        self.assertIsNotNone(p.poll())  # process exited with exit code


if __name__ == "__main__":
    unittest.main()
