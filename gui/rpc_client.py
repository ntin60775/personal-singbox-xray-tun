from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class RPCError(Exception):
    """Raised when the backend returns a JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class SubvostRPCClient:
    """JSON-RPC client that communicates with the subvostd Go backend
    via stdin/stdout of a long-lived subprocess."""

    def __init__(self, backend_cmd: list[str] | None = None) -> None:
        self._backend_cmd = backend_cmd or self._default_backend_cmd()
        self._proc: subprocess.Popen | None = None
        self._id = 0

    @staticmethod
    def _default_backend_cmd() -> list[str]:
        """Locate subvostd binary relative to this file's project root."""
        gui_dir = Path(__file__).resolve().parent
        project_root = gui_dir.parent
        candidate = project_root / "subvostd"
        if candidate.exists():
            return [str(candidate), "--mode", "serve"]

        # Try PATH
        return ["subvostd", "--mode", "serve"]

    def _ensure_proc(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        self._proc = subprocess.Popen(
            self._backend_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        self._ensure_proc()
        assert self._proc is not None
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None

        self._id += 1
        req = {"id": self._id, "method": method, "params": params or {}}
        request_line = json.dumps(req, ensure_ascii=False) + "\n"
        self._proc.stdin.write(request_line)
        self._proc.stdin.flush()

        response_line = self._proc.stdout.readline()
        if not response_line:
            raise ConnectionError("Backend process closed stdout")

        resp = json.loads(response_line)
        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            raise RPCError(code=err.get("code", -1), message=err.get("message", "Unknown error"))

        return resp.get("result")

    def shutdown(self) -> None:
        """Send shutdown and wait for the backend to exit."""
        try:
            self.call("shutdown")
        except (ConnectionError, OSError):
            pass
        if self._proc is not None:
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    def close(self) -> None:
        """Gracefully stop the backend on client close."""
        if self._proc is not None and self._proc.poll() is None:
            try:
                self.shutdown()
            except Exception:
                self._proc.kill()
                self._proc.wait()

    def __enter__(self) -> SubvostRPCClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ----- Convenience accessors matching the old SubvostAppService API -----

class RPCAccessors:
    """Provides named accessors that mirror SubvostAppService methods.

    Each method translates to a JSON-RPC call on the client.
    """

    def __init__(self, client: SubvostRPCClient) -> None:
        self._client = client

    # Runtime
    def status(self) -> dict[str, Any]:
        return self._client.call("status")  # type: ignore[return-value]

    def start(self) -> dict[str, Any]:
        return self._client.call("start")  # type: ignore[return-value]

    def stop(self) -> dict[str, Any]:
        return self._client.call("stop")  # type: ignore[return-value]

    def capture_diagnostics(self) -> dict[str, Any]:
        return self._client.call("diagnostics.capture")  # type: ignore[return-value]

    # Nodes
    def nodes_list(self) -> dict[str, Any]:
        return self._client.call("nodes.list")  # type: ignore[return-value]

    def nodes_activate(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._client.call("nodes.activate", {"profile_id": profile_id, "node_id": node_id})  # type: ignore[return-value]

    def nodes_delete(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._client.call("nodes.delete", {"profile_id": profile_id, "node_id": node_id})  # type: ignore[return-value]

    # Subscriptions
    def subscriptions_list(self) -> dict[str, Any]:
        return self._client.call("subscriptions.list")  # type: ignore[return-value]

    def subscriptions_add(self, name: str, url: str) -> dict[str, Any]:
        return self._client.call("subscriptions.add", {"name": name, "url": url})  # type: ignore[return-value]

    def subscriptions_refresh(self, subscription_id: str) -> dict[str, Any]:
        return self._client.call("subscriptions.refresh", {"subscription_id": subscription_id})  # type: ignore[return-value]

    def subscriptions_refresh_all(self) -> dict[str, Any]:
        return self._client.call("subscriptions.refresh_all")  # type: ignore[return-value]

    def subscriptions_delete(self, subscription_id: str) -> dict[str, Any]:
        return self._client.call("subscriptions.delete", {"subscription_id": subscription_id})  # type: ignore[return-value]

    # Profiles
    def profiles_list(self) -> dict[str, Any]:
        return self._client.call("profiles.list")  # type: ignore[return-value]

    def profiles_delete(self, profile_id: str) -> dict[str, Any]:
        return self._client.call("profiles.delete", {"profile_id": profile_id})  # type: ignore[return-value]

    # Routing
    def routing_profiles_list(self) -> dict[str, Any]:
        return self._client.call("routing.profiles.list")  # type: ignore[return-value]

    def routing_profiles_import(self, text: str) -> dict[str, Any]:
        return self._client.call("routing.profiles.import", {"text": text})  # type: ignore[return-value]

    def routing_profiles_activate(self, profile_id: str) -> dict[str, Any]:
        return self._client.call("routing.profiles.activate", {"profile_id": profile_id})  # type: ignore[return-value]

    def routing_profiles_clear(self) -> dict[str, Any]:
        return self._client.call("routing.profiles.clear")  # type: ignore[return-value]

    def routing_enabled_set(self, enabled: bool) -> dict[str, Any]:
        return self._client.call("routing.enabled.set", {"enabled": enabled})  # type: ignore[return-value]

    def routing_geodata_prepare(self) -> dict[str, Any]:
        return self._client.call("routing.geodata.prepare")  # type: ignore[return-value]

    # Links
    def links_import(self, text: str) -> dict[str, Any]:
        return self._client.call("links.import", {"text": text})  # type: ignore[return-value]

    # Ping
    def ping(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._client.call("ping", {"profile_id": profile_id, "node_id": node_id})  # type: ignore[return-value]

    # Settings
    def settings_get(self) -> dict[str, Any]:
        return self._client.call("settings.get")  # type: ignore[return-value]

    def settings_save(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._client.call("settings.save", {"settings": settings})  # type: ignore[return-value]

    # Artifacts
    def artifacts_cleanup(self) -> dict[str, Any]:
        return self._client.call("artifacts.cleanup")  # type: ignore[return-value]

    def artifacts_audit(self) -> dict[str, Any]:
        return self._client.call("artifacts.audit")  # type: ignore[return-value]

    # System
    def store_snapshot(self) -> dict[str, Any]:
        return self._client.call("store.snapshot")  # type: ignore[return-value]
