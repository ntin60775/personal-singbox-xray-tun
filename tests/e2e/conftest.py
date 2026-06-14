from __future__ import annotations

import pytest


def pytest_configure(config):
    """Configure pytest-asyncio for async tests."""
    config.option.asyncio_mode = "auto"

"""
Shared fixtures for e2e TUI tests.

Provides:
- FakeService: a SubvostAppService-compatible object that uses real Python store
  in a temp directory, but mocks all RPC/HTTP operations.
- fake_app: pytest fixture returning a SubvostTUI instance with injected FakeService.
"""


import base64
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# -- Patch RPC and HTTP before any GUI imports --
# We must do this BEFORE importing the TUI or service modules,
# otherwise they try to spawn subvostd at import time.


def _make_fake_vless_links(count: int = 5) -> str:
    """Generate a realistic VLESS subscription payload with N nodes."""
    lines = []
    for i in range(count):
        uid = str(uuid.uuid4())
        # VLESS reality xhttp link (typical provider format)
        link = (
            f"vless://{uid}@1.2.3.{10 + i}:443"
            f"?encryption=none&security=reality&flow=xtls-rprx-vision"
            f"&sni=yahoo.com&fp=chrome&pbk=some-public-key-{i}"
            f"&sid=shortid{i:02d}&type=xhttp&host=cdn-{i}.example.com"
            f"&path=/vless&mode=auto"
            f"#Node-{i + 1:02d}"
        )
        lines.append(link)
    return "\n".join(lines)


FAKE_SUBSCRIPTION_PAYLOAD = _make_fake_vless_links(7)


class FakeHTTPResponse:
    """Fake urllib response for subscription payload."""

    def __init__(self, payload: str, headers: dict | None = None, status: int = 200):
        self._payload = payload.encode("utf-8")
        self.status = status
        self._headers = headers or {}
        self.reason = "OK" if status == 200 else "Error"

    def read(self) -> bytes:
        return self._payload

    def getheader(self, name: str, default: str = "") -> str:
        return self._headers.get(name, default)

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class FakeService:
    """
    Replaces SubvostAppService for e2e testing.

    Uses the real Python store (subvost_store module) but:
    - Redirects store to a temp directory
    - Returns fake data for all RPC operations (status, logs, runtime, etc.)
    - Mocks HTTP subscription refresh
    - Never spawns subvostd
    """

    def __init__(self, store_dir: Path, project_root: Path) -> None:
        self._store_dir = store_dir
        self._project_root = project_root
        # Set up paths as if XDG_CONFIG_HOME is store_dir's parent
        self._paths = self._build_paths()
        self._store_dir.mkdir(parents=True, exist_ok=True)
        # Pre-seed the store with empty structure
        self._ensure_store()

    def _build_paths(self) -> Any:
        from gui.subvost_paths import AppPaths

        store_dir = self._store_dir
        xray_asset_dir = store_dir / "xray-assets"
        return AppPaths(
            real_home=store_dir.parent,
            config_home=store_dir.parent,
            store_dir=store_dir,
            store_file=store_dir / "store.json",
            gui_settings_file=store_dir / "gui-settings.json",
            generated_xray_config_file=store_dir / "generated-xray-config.json",
            active_runtime_xray_config_file=store_dir / "active-runtime-xray-config.json",
            xray_asset_dir=xray_asset_dir,
            geoip_asset_file=xray_asset_dir / "geoip.dat",
            geosite_asset_file=xray_asset_dir / "geosite.dat",
        )
    def _ensure_store(self) -> dict[str, Any]:
        from gui.subvost_store import ensure_store_initialized

        # Copy Xray template to store dir if needed
        src_template = self._project_root / "xray-tun-subvost.json"
        dst_template = self._store_dir / "xray-config-template.json"
        if not dst_template.exists() and src_template.exists():
            shutil.copy2(str(src_template), str(dst_template))

        store = ensure_store_initialized(self._paths, self._project_root)
        return store

    def _load_store(self) -> dict[str, Any]:
        from gui.subvost_store import load_store
        return load_store(self._paths)

    def _save_store(self, store: dict[str, Any]) -> None:
        from gui.subvost_store import save_store
        save_store(self._paths, store)

    # ---- Store operations (Python side, real) ----

    def ensure_store_ready(self) -> dict[str, Any]:
        return self._ensure_store()

    def persist_store(self, store: dict[str, Any]) -> None:
        self._save_store(store)

    def load_settings(self) -> dict[str, Any]:
        from gui.subvost_store import read_gui_settings
        return read_gui_settings(self._paths)

    def save_settings(
        self,
        file_logs_enabled: bool | None = None,
        *,
        close_to_tray: bool | None = None,
        start_minimized_to_tray: bool | None = None,
        theme: str | None = None,
        artifact_retention_days: int | None = None,
    ) -> None:
        from gui.subvost_store import save_gui_settings
        save_gui_settings(
            self._paths,
            file_logs_enabled,
            close_to_tray=close_to_tray,
            start_minimized_to_tray=start_minimized_to_tray,
            theme=theme,
            artifact_retention_days=artifact_retention_days,
        )

    # ---- Subscription operations ----

    def add_subscription(self, name: str, url: str) -> dict[str, Any]:
        """Add subscription: create subscription + linked profile in store."""
        store = self._load_store()
        sub_id = f"sub-{uuid.uuid4().hex[:12]}"
        profile_id = f"profile-{uuid.uuid4().hex[:12]}"

        subscription = {
            "id": sub_id,
            "url": url,
            "name": name,
            "enabled": True,
            "etag": "",
            "last_modified": "",
            "last_success_at": None,
            "last_status": "never",
            "last_error": "",
            "profile_id": profile_id,
            "provider_id": "",
            "provider_id_source": "",
            "routing_profile_id": None,
            "last_routing_status": "never",
            "last_routing_error": "",
        }
        profile = {
            "id": profile_id,
            "kind": "subscription",
            "name": name,
            "enabled": True,
            "source_subscription_id": sub_id,
            "nodes": [],
        }
        store["subscriptions"].append(subscription)
        store["profiles"].append(profile)
        self._save_store(store)
        return {"ok": True, "subscription": subscription}

    def refresh_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Simulate subscription refresh with fake nodes."""
        store = self._load_store()

        # Find subscription
        sub = None
        for s in store.get("subscriptions", []):
            if s.get("id") == subscription_id:
                sub = s
                break
        if sub is None:
            return {"ok": False, "error": "Subscription not found"}

        profile_id = sub.get("profile_id")
        if not profile_id:
            return {"ok": False, "error": "No linked profile"}

        # Parse fake nodes from payload
        from gui.subvost_parser import ParseError, parse_proxy_uri, parse_subscription_payload

        links, fmt = parse_subscription_payload(FAKE_SUBSCRIPTION_PAYLOAD.encode("utf-8"))

        # Find profile
        profile = None
        for p in store.get("profiles", []):
            if p.get("id") == profile_id:
                profile = p
                break
        if profile is None:
            return {"ok": False, "error": "Profile not found"}

        from gui.subvost_store import _make_node_record

        for line in links:
            try:
                normalized = parse_proxy_uri(line)
            except ParseError:
                continue
            record = _make_node_record(
                normalized,
                origin_kind="subscription",
                subscription_id=subscription_id,
                name=normalized.get("display_name", "Unnamed"),
                raw_uri=line,
            )
            # Deduplicate by fingerprint
            existing = [n for n in profile["nodes"] if n.get("fingerprint") == record.get("fingerprint")]
            if not existing:
                profile["nodes"].append(record)

        # Update subscription metadata
        sub["last_status"] = "ok"
        sub["last_success_at"] = "2026-06-13T00:00:00"
        sub["last_error"] = ""

        self._save_store(store)
        return {"ok": True, "subscription": sub}

    def refresh_all_subscriptions(self) -> dict[str, Any]:
        store = self._load_store()
        results = []
        for sub in list(store.get("subscriptions", [])):
            if sub.get("enabled", True):
                result = self.refresh_subscription(sub.get("id"))
                results.append(result)
        return {"ok": True, "results": results}

    def delete_subscription(self, subscription_id: str) -> dict[str, Any]:
        from gui.subvost_store import delete_subscription as store_delete

        store = self._load_store()
        store_delete(store, subscription_id)
        self._save_store(store)
        return {"ok": True}

    def update_subscription(
        self, subscription_id: str, *, name: str | None = None, enabled: bool | None = None
    ) -> dict[str, Any]:
        from gui.subvost_store import update_subscription as store_update

        store = self._load_store()
        sub = store_update(store, subscription_id, name=name, enabled=enabled)
        self._save_store(store)
        return {"ok": True, "subscription": sub}

    # ---- Node/profile operations ----

    def activate_selection(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self._load_store()
        # Set active selection
        store["active_selection"] = {
            "profile_id": profile_id,
            "node_id": node_id,
            "activated_at": "2026-06-13T00:00:00",
            "source": "manual",
        }
        self._save_store(store)
        return {"ok": True}

    def ping_node_by_id(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return {"ok": True, "latency_ms": 42, "latency_display": "42 мс"}

    def delete_node(self, profile_id: str, node_id: str) -> dict[str, Any]:
        store = self._load_store()
        for profile in store.get("profiles", []):
            if profile.get("id") == profile_id:
                profile["nodes"] = [n for n in profile.get("nodes", []) if n.get("id") != node_id]
                break
        self._save_store(store)
        return {"ok": True}

    def update_node(
        self, profile_id: str, node_id: str, *, name: str | None = None, enabled: bool | None = None
    ) -> dict[str, Any]:
        from gui.subvost_store import update_node as store_update

        store = self._load_store()
        node = store_update(store, profile_id, node_id, name=name, enabled=enabled)
        self._save_store(store)
        return {"ok": True, "node": node}

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        from gui.subvost_store import delete_profile as store_delete

        store = self._load_store()
        store_delete(store, profile_id)
        self._save_store(store)
        return {"ok": True}

    def update_profile(
        self, profile_id: str, *, name: str | None = None, enabled: bool | None = None
    ) -> dict[str, Any]:
        from gui.subvost_store import update_profile as store_update

        store = self._load_store()
        profile = store_update(store, profile_id, name=name, enabled=enabled)
        self._save_store(store)
        return {"ok": True, "profile": profile}

    # ---- Routing operations ----

    def import_routing_profile(self, text: str) -> dict[str, Any]:
        from gui.subvost_store import import_routing_profile as store_import

        store = self._load_store()
        result = store_import(store, self._paths, text)
        self._save_store(store)
        return result

    def activate_routing_profile(self, profile_id: str) -> dict[str, Any]:
        store = self._load_store()
        routing = store.setdefault("routing", {})
        routing["active_profile_id"] = profile_id
        routing["enabled"] = True
        self._save_store(store)
        return {"ok": True}

    def clear_active_routing_profile(self) -> dict[str, Any]:
        store = self._load_store()
        routing = store.setdefault("routing", {})
        routing["active_profile_id"] = None
        routing["enabled"] = False
        self._save_store(store)
        return {"ok": True}

    def set_routing_enabled(self, enabled: bool) -> dict[str, Any]:
        store = self._load_store()
        routing = store.setdefault("routing", {})
        routing["enabled"] = enabled
        self._save_store(store)
        return {"ok": True}

    def prepare_routing_geodata(self) -> dict[str, Any]:
        return {"ok": True, "geoip_updated": False, "geosite_updated": False}

    # ---- Runtime / status operations (fake) ----

    def collect_status(self) -> dict[str, Any]:
        return {
            "processes": {
                "xray_alive": False,
                "xray_pid": None,
                "tun_present": False,
                "tun_interface": "tun0",
                "ownership": "self",
            },
            "state_file": {},
            "traffic": {"rx_bytes": 0, "tx_bytes": 0, "rx_rate": 0, "tx_rate": 0},
            "active_node": None,
            "active_profile": None,
            "routing": {"active_profile_id": None, "active_profile_name": None},
        }

    def collect_store_snapshot(self) -> dict[str, Any]:
        store = self._load_store()
        return {"store": store}

    def collect_log_payload(self) -> dict[str, Any]:
        return {"entries": []}

    def start_runtime(self) -> dict[str, Any]:
        return {"ok": True, "message": "Runtime started (fake)"}

    def stop_runtime(self) -> dict[str, Any]:
        return {"ok": True, "message": "Runtime stopped (fake)"}

    def capture_diagnostics(self) -> dict[str, Any]:
        return {"ok": True, "output": "fake diagnostics"}

    def takeover_runtime(self) -> dict[str, Any]:
        return {"ok": True}

    def cleanup_runtime_artifacts(self) -> dict[str, Any]:
        return {"ok": True, "removed": []}

    def terminate_app(self, source: str = "window-close") -> dict[str, Any]:
        return {"ok": True, "vpn_stop_requested": False, "status": self.collect_status()}

    def shutdown_gui(self, source: str = "window-close") -> dict[str, Any]:
        return {"ok": True, "vpn_stop_requested": False, "status": self.collect_status()}

    def update_xray_core(self) -> dict[str, Any]:
        return {"ok": True}

    # ---- State inspection ----

    def runtime_control_blocked(self, runtime_info: dict[str, Any]) -> bool:
        return False

    def runtime_stop_required(self, state: dict[str, str] | None = None) -> bool:
        return False

    def inspect_runtime_state(self, state: dict[str, str] | None = None) -> dict[str, Any]:
        return {"xray_alive": False, "tun_present": False, "stack_is_live": False}

    def find_profile_and_node(self, store: dict[str, Any], profile_id: str, node_id: str) -> tuple:
        for profile in store.get("profiles", []):
            if profile.get("id") != profile_id:
                continue
            for node in profile.get("nodes", []):
                if node.get("id") == node_id:
                    return profile, node
            return profile, None
        return None, None

    def __del__(self) -> None:
        pass  # No subprocess to clean up


@pytest.fixture
def temp_store_dir(tmp_path: Path) -> Path:
    """Temporary directory for the store."""
    store_dir = tmp_path / "subvost-xray-tun"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


@pytest.fixture
def project_root() -> Path:
    """Absolute path to the project root (where xray-tun-subvost.json lives)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def fake_service(temp_store_dir: Path, project_root: Path) -> FakeService:
    """Create a FakeService pointing at a temp store."""
    return FakeService(store_dir=temp_store_dir, project_root=project_root)


@pytest.fixture
def mock_urlopen():
    """Mock urllib.request.urlopen to return fake subscription data."""
    with patch("urllib.request.urlopen") as mock:
        # Encode as base64 (standard subscription format)
        payload_b64 = base64.b64encode(FAKE_SUBSCRIPTION_PAYLOAD.encode()).decode()
        mock.return_value = FakeHTTPResponse(payload_b64)
        yield mock


@pytest.fixture
def mock_rpc_client():
    """Mock SubvostRPCClient to never spawn subprocesses."""
    with patch("gui.rpc_client.SubvostRPCClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        mock_cls.return_value.call = MagicMock(return_value={"ok": True})
        mock_cls.return_value.close = MagicMock()
        mock_cls.return_value.shutdown = MagicMock()
        yield mock_cls


class FakeRuntimeAdapter:
    """Mock ShellRuntimeAdapter — все операции возвращают успех без pkexec."""

    def start_runtime(self, service):
        return {"ok": True, "output": "fake start"}

    def stop_runtime(self, service):
        return {"ok": True, "output": "fake stop"}

    def diagnose(self, service):
        return {"ok": True, "output": "fake diag"}



def make_test_app(service: FakeService) -> SubvostTUI:
    """Create SubvostTUI with fake service and runtime adapter for testing."""
    from gui.tui_app import SubvostTUI
    return SubvostTUI(service=service, runtime_adapter=FakeRuntimeAdapter())

@pytest.fixture
def mock_store_urlopen():
    """Mock urllib.request.urlopen specifically for store module paths.

    The TUI's _action_refresh_sub calls the real subvost_store.refresh_subscription
    which uses urllib.request.urlopen. This fixture patches the correct import path.
    """
    import base64 as _b64
    from unittest.mock import MagicMock

    payload_b64 = _b64.b64encode(FAKE_SUBSCRIPTION_PAYLOAD.encode()).decode()
    fake_response = MagicMock()
    fake_response.read.return_value = payload_b64.encode("utf-8")
    fake_response.status = 200
    fake_response.headers = {}
    fake_response.getheader.return_value = ""
    # Context manager protocol for `with urlopen(...) as response:`
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=fake_response):
        yield
