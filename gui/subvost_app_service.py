from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from gui.presentation.view_models import (
    build_view_model,
    humanize_bytes,
    humanize_rate,
)
from infrastructure.adapters import ShellRuntimeAdapter, SystemNetworkAdapter
from infrastructure.json_repositories import (
    JsonNodeRepository,
    JsonSubscriptionRepository,
)
from rpc_client import RPCError, SubvostRPCClient

# Re-export for TUI compatibility
from subvost_parser import preview_links
from subvost_paths import APP_DIRNAME, resolve_config_home
from subvost_store import (
    clear_active_routing_profile as store_clear_active_routing_profile,
    delete_profile as store_delete_profile,
    delete_subscription as store_delete_subscription,
    ensure_store_initialized,
    import_routing_profile as store_import_routing_profile,
    load_store,
    prepare_routing_runtime as store_prepare_routing_runtime,
    read_gui_settings,
    refresh_subscription as store_refresh_subscription,
    refresh_all_subscriptions as store_refresh_all_subscriptions,
    save_gui_settings,
    save_manual_import_results,
    save_store,
    set_routing_enabled as store_set_routing_enabled,
    store_payload,
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


class SubvostAppService:
    """RPC-backed compatibility shim for SubvostAppService.

    Delegates runtime operations to the Go subvostd backend via JSON-RPC.
    Store operations (CRUD) still use the Python store module for transition.
    """

    def __init__(
        self,
        service: Any = None,
        *,
        backend_cmd: list[str] | None = None,
    ) -> None:
        # Support old __init__ signature (service arg ignored)
        self._rpc = SubvostRPCClient(backend_cmd)

        # Keep adapters for operations still handled in Python
        self.runtime_adapter = ShellRuntimeAdapter(
            project_root=PROJECT_ROOT,
            libexec_dir=PROJECT_ROOT / "libexec",
        )
        self.network_adapter = SystemNetworkAdapter()

    # ---- Store operations (Python-side, shared store.json) ----

    def ensure_store_ready(self) -> dict[str, Any]:
        return ensure_store_initialized(
            build_app_paths(),
            PROJECT_ROOT,
        )

    def persist_store(self, store: dict[str, Any]) -> None:
        save_store(build_app_paths(), store)

    def load_settings(self) -> dict[str, Any]:
        return read_gui_settings(build_app_paths())

    def save_settings(
        self,
        file_logs_enabled: bool | None = None,
        *,
        close_to_tray: bool | None = None,
        start_minimized_to_tray: bool | None = None,
        theme: str | None = None,
        artifact_retention_days: int | None = None,
    ) -> None:
        save_gui_settings(
            build_app_paths(),
            file_logs_enabled,
            close_to_tray=close_to_tray,
            start_minimized_to_tray=start_minimized_to_tray,
            theme=theme,
            artifact_retention_days=artifact_retention_days,
        )

    # ---- Subscription operations ----

    def add_subscription(self, name: str, url: str) -> dict[str, Any]:
        """Add subscription via Go backend (handles full lifecycle)."""
        return self._rpc.call("subscriptions.add", {"name": name, "url": url})

    def refresh_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._rpc.call("subscriptions.refresh", {"subscription_id": subscription_id})

    def refresh_all_subscriptions(self) -> dict[str, Any]:
        return self._rpc.call("subscriptions.refresh_all")

    def delete_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._rpc.call("subscriptions.delete", {"subscription_id": subscription_id})

    def update_subscription(
        self, subscription_id: str, *, name: str | None = None, enabled: bool | None = None
    ) -> dict[str, Any]:
        # Use Python store for now (Go supports basic update via RPC)
        store = self.ensure_store_ready()
        from subvost_store import update_subscription as store_update
        sub = store_update(store, subscription_id, name=name, enabled=enabled)
        self.persist_store(store)
        return {"ok": True, "subscription": sub}

    # ---- Node/profile operations ----

    def activate_selection(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._rpc.call("nodes.activate", {"profile_id": profile_id, "node_id": node_id})

    def ping_node_by_id(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._rpc.call("ping", {"profile_id": profile_id, "node_id": node_id})

    def delete_node(self, profile_id: str, node_id: str) -> dict[str, Any]:
        return self._rpc.call("nodes.delete", {"profile_id": profile_id, "node_id": node_id})

    def update_node(
        self, profile_id: str, node_id: str, *, name: str | None = None, enabled: bool | None = None
    ) -> dict[str, Any]:
        store = self.ensure_store_ready()
        from subvost_store import update_node as store_update
        node = store_update(store, profile_id, node_id, name=name, enabled=enabled)
        self.persist_store(store)
        return {"ok": True, "node": node}

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        store_delete_profile(store, profile_id)
        self.persist_store(store)
        return {"ok": True}

    def update_profile(self, profile_id: str, *, name: str | None = None, enabled: bool | None = None) -> dict[str, Any]:
        store = self.ensure_store_ready()
        from subvost_store import update_profile as store_update
        profile = store_update(store, profile_id, name=name, enabled=enabled)
        self.persist_store(store)
        return {"ok": True, "profile": profile}

    # ---- Routing operations ----

    def import_routing_profile(self, text: str) -> dict[str, Any]:
        store = self.ensure_store_ready()
        result = store_import_routing_profile(store, build_app_paths(), text)
        self.persist_store(store)
        return result

    def activate_routing_profile(self, profile_id: str) -> dict[str, Any]:
        return self._rpc.call("routing.profiles.activate", {"profile_id": profile_id})

    def clear_active_routing_profile(self) -> dict[str, Any]:
        return self._rpc.call("routing.profiles.clear")

    def set_routing_enabled(self, enabled: bool) -> dict[str, Any]:
        return self._rpc.call("routing.enabled.set", {"enabled": enabled})

    def prepare_routing_geodata(self) -> dict[str, Any]:
        return self._rpc.call("routing.geodata.prepare")

    # ---- Runtime operations (RPC) ----

    def collect_status(self) -> dict[str, Any]:
        return self._rpc.call("status")

    def collect_store_snapshot(self) -> dict[str, Any]:
        return self._rpc.call("store.snapshot")

    def collect_log_payload(self) -> dict[str, Any]:
        return self._rpc.call("diagnostics.capture")

    def start_runtime(self) -> dict[str, Any]:
        return self._rpc.call("start")

    def stop_runtime(self) -> dict[str, Any]:
        return self._rpc.call("stop")

    def capture_diagnostics(self) -> dict[str, Any]:
        return self._rpc.call("diagnostics.capture")

    def takeover_runtime(self) -> dict[str, Any]:
        return self._rpc.call("stop")

    def cleanup_runtime_artifacts(self) -> dict[str, Any]:
        return self._rpc.call("artifacts.cleanup")

    def terminate_app(self, source: str = "window-close") -> dict[str, Any]:
        result = self._rpc.call("status")
        return {
            "ok": True,
            "message": "Приложение закрывается.",
            "shutdown_source": source,
            "vpn_stop_requested": result.get("processes", {}).get("xray_alive", False),
            "status": result,
        }

    def shutdown_gui(self, source: str = "window-close") -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Графический интерфейс закрывается без остановки VPN-подключения.",
            "shutdown_source": source,
            "vpn_stop_requested": False,
            "status": self._rpc.call("status"),
        }

    def update_xray_core(self) -> dict[str, Any]:
        return self._rpc.call("status")

    def runtime_control_blocked(self, runtime_info: dict[str, Any]) -> bool:
        ownership = runtime_info.get("ownership", "unknown")
        if ownership in ("foreign", "unknown"):
            return bool(runtime_info.get("stack_is_live", False))
        return False

    def runtime_stop_required(self, state: dict[str, str] | None = None) -> bool:
        status = self._rpc.call("status")
        return bool(status.get("processes", {}).get("xray_alive", False))

    def inspect_runtime_state(self, state: dict[str, str] | None = None) -> dict[str, Any]:
        status = self._rpc.call("status")
        procs = status.get("processes", {})
        return {
            "state": status.get("state_file", {}),
            "has_state": bool(procs.get("xray_pid")),
            "ownership": procs.get("ownership", "unknown"),
            "tun_interface": procs.get("tun_interface", "tun0"),
            "xray_pid": procs.get("xray_pid"),
            "xray_alive": procs.get("xray_alive", False),
            "tun_present": procs.get("tun_present", False),
            "stack_is_live": procs.get("xray_alive", False) or procs.get("tun_present", False),
            "owned_stack_is_live": procs.get("xray_alive", False),
        }

    def find_profile_and_node(self, store: dict[str, Any], profile_id: str, node_id: str) -> tuple[Any, Any]:
        for profile in store.get("profiles", []):
            if profile.get("id") != profile_id:
                continue
            for node in profile.get("nodes", []):
                if node.get("id") == node_id:
                    return profile, node
            return profile, None
        return None, None

    # ---- Cleanup ----

    def __del__(self) -> None:
        try:
            if hasattr(self, "_rpc"):
                self._rpc.close()
        except Exception:
            pass


def build_app_paths() -> Any:
    """Build AppPaths for the Python store module."""
    from subvost_paths import build_app_paths as _build
    return _build(Path.home())


def build_default_service(gui_dir: Path) -> SubvostAppService:
    """Factory function matching the original build_default_service signature."""
    return SubvostAppService()
