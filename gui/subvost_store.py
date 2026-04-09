from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_DNS, uuid4, uuid5

from subvost_parser import ParseError, parse_proxy_uri, parse_subscription_payload
from subvost_paths import AppPaths, atomic_write_json, ensure_store_dir, read_json_file, remove_file_if_exists
from subvost_routing import (
    RoutingProfileError,
    build_geodata_status,
    download_routing_geodata,
    get_existing_geodata_status,
    parse_routing_profile_input,
    routing_profile_rule_count,
)
from subvost_runtime import node_can_render_runtime, read_json_config, render_runtime_config


STORE_VERSION = 2
MANUAL_PROFILE_ID = "manual"
MANUAL_PROFILE_NAME = "Локальные ссылки"
DEFAULT_SUBSCRIPTION_USER_AGENT = os.environ.get("SUBVOST_SUBSCRIPTION_USER_AGENT", "Xray-core")


def default_subscription_hwid() -> str:
    explicit = os.environ.get("SUBVOST_SUBSCRIPTION_HWID", "").strip()
    if explicit:
        return explicit

    real_home = os.environ.get("SUBVOST_REAL_HOME", "").strip()
    home_part = real_home or str(Path.home())
    seed = "|".join(
        part
        for part in [
            socket.gethostname().strip(),
            home_part,
            platform.system().strip(),
            platform.machine().strip(),
        ]
        if part
    )
    return str(uuid5(NAMESPACE_DNS, seed or "subvost-xray-tun"))


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def default_store() -> dict[str, Any]:
    return {
        "version": STORE_VERSION,
        "profiles": [
            {
                "id": MANUAL_PROFILE_ID,
                "kind": "manual",
                "name": MANUAL_PROFILE_NAME,
                "enabled": True,
                "source_subscription_id": None,
                "nodes": [],
            }
        ],
        "subscriptions": [],
        "active_selection": {
            "profile_id": None,
            "node_id": None,
            "activated_at": None,
            "source": None,
        },
        "routing": {
            "enabled": False,
            "active_profile_id": None,
            "profiles": [],
            "runtime_ready": False,
            "runtime_error": "",
            "geodata": default_routing_geodata_state(),
        },
        "meta": {
            "initialized_at": iso_now(),
        },
    }


def default_routing_geodata_state() -> dict[str, Any]:
    return {
        "status": "inactive",
        "ready": False,
        "error": "",
        "geoip_url": "",
        "geosite_url": "",
        "geoip_path": "",
        "geosite_path": "",
        "asset_dir": "",
        "geoip_exists": False,
        "geosite_exists": False,
    }


def _normalize_routing_profile(profile: dict[str, Any]) -> dict[str, Any]:
    now = iso_now()
    name = str(profile.get("name") or "").strip()
    raw_payload = profile.get("raw_payload")
    if not isinstance(raw_payload, dict):
        raw_payload = {}
    return {
        "id": str(profile.get("id") or f"routing-{uuid4().hex}"),
        "name": name,
        "name_key": str(profile.get("name_key") or name.casefold()),
        "enabled": bool(profile.get("enabled", True)),
        "source_format": str(profile.get("source_format") or "json"),
        "raw_payload": raw_payload,
        "global_proxy": bool(profile.get("global_proxy", False)),
        "domain_strategy": str(profile.get("domain_strategy") or "AsIs"),
        "geoip_url": str(profile.get("geoip_url") or ""),
        "geosite_url": str(profile.get("geosite_url") or ""),
        "direct_sites": [str(item).strip() for item in profile.get("direct_sites", []) if str(item).strip()],
        "direct_ip": [str(item).strip() for item in profile.get("direct_ip", []) if str(item).strip()],
        "proxy_sites": [str(item).strip() for item in profile.get("proxy_sites", []) if str(item).strip()],
        "proxy_ip": [str(item).strip() for item in profile.get("proxy_ip", []) if str(item).strip()],
        "block_sites": [str(item).strip() for item in profile.get("block_sites", []) if str(item).strip()],
        "block_ip": [str(item).strip() for item in profile.get("block_ip", []) if str(item).strip()],
        "dns_hosts": dict(profile.get("dns_hosts") or {}),
        "domestic_dns_domain": str(profile.get("domestic_dns_domain") or ""),
        "domestic_dns_ip": str(profile.get("domestic_dns_ip") or ""),
        "domestic_dns_type": str(profile.get("domestic_dns_type") or ""),
        "remote_dns_domain": str(profile.get("remote_dns_domain") or ""),
        "remote_dns_ip": str(profile.get("remote_dns_ip") or ""),
        "remote_dns_type": str(profile.get("remote_dns_type") or ""),
        "fake_dns": bool(profile.get("fake_dns", False)),
        "route_order": list(profile.get("route_order") or ["block", "direct", "proxy"]),
        "last_updated": str(profile.get("last_updated") or ""),
        "supported_entry_count": int(profile.get("supported_entry_count", routing_profile_rule_count(profile))),
        "stored_only_fields": [str(item) for item in profile.get("stored_only_fields", []) if str(item).strip()],
        "ignored_fields": [str(item) for item in profile.get("ignored_fields", []) if str(item).strip()],
        "unknown_fields": [str(item) for item in profile.get("unknown_fields", []) if str(item).strip()],
        "created_at": str(profile.get("created_at") or now),
        "updated_at": str(profile.get("updated_at") or profile.get("created_at") or now),
    }


def ensure_store_structure(store: dict[str, Any]) -> dict[str, Any]:
    if not store:
        store = default_store()
    routing = store.get("routing") or {}
    store = {
        "version": STORE_VERSION,
        "profiles": store.get("profiles", []),
        "subscriptions": store.get("subscriptions", []),
        "active_selection": store.get("active_selection")
        or {"profile_id": None, "node_id": None, "activated_at": None, "source": None},
        "routing": {
            "enabled": bool(routing.get("enabled", False)),
            "active_profile_id": routing.get("active_profile_id"),
            "profiles": [_normalize_routing_profile(item) for item in routing.get("profiles", []) if isinstance(item, dict)],
            "runtime_ready": bool(routing.get("runtime_ready", False)),
            "runtime_error": str(routing.get("runtime_error") or ""),
            "geodata": {**default_routing_geodata_state(), **(routing.get("geodata") or {})},
        },
        "meta": store.get("meta") or {},
    }
    store["meta"].setdefault("initialized_at", iso_now())
    if not any(profile.get("id") == MANUAL_PROFILE_ID for profile in store["profiles"]):
        store["profiles"].insert(
            0,
            {
                "id": MANUAL_PROFILE_ID,
                "kind": "manual",
                "name": MANUAL_PROFILE_NAME,
                "enabled": True,
                "source_subscription_id": None,
                "nodes": [],
            },
        )
    for profile in store["profiles"]:
        profile.setdefault("enabled", True)
        profile.setdefault("source_subscription_id", None)
        profile.setdefault("nodes", [])
        for node in profile["nodes"]:
            node.setdefault("enabled", True)
            node.setdefault("user_renamed", False)
            node.setdefault("parse_error", "")
            node.setdefault("origin", {"kind": profile.get("kind", "manual")})
            node.setdefault("created_at", iso_now())
            node.setdefault("updated_at", node["created_at"])

    valid_routing_ids = {profile["id"] for profile in store["routing"]["profiles"] if profile.get("name")}
    active_routing_id = store["routing"].get("active_profile_id")
    if active_routing_id not in valid_routing_ids:
        store["routing"]["active_profile_id"] = None
        store["routing"]["enabled"] = False
    else:
        active_routing_profile = next(
            (profile for profile in store["routing"]["profiles"] if profile["id"] == active_routing_id),
            None,
        )
        if active_routing_profile and not active_routing_profile.get("enabled", True):
            store["routing"]["active_profile_id"] = None
            store["routing"]["enabled"] = False

    for subscription in store["subscriptions"]:
        subscription.setdefault("enabled", True)
        subscription.setdefault("etag", "")
        subscription.setdefault("last_modified", "")
        subscription.setdefault("last_success_at", None)
        subscription.setdefault("last_status", "never")
        subscription.setdefault("last_error", "")
        subscription.setdefault("profile_id", None)
    return store

def save_store(paths: AppPaths, store: dict[str, Any], uid: int | None = None, gid: int | None = None) -> None:
    ensure_store_dir(paths, uid=uid, gid=gid)
    atomic_write_json(paths.store_file, ensure_store_structure(store), uid=uid, gid=gid)


def load_store(paths: AppPaths) -> dict[str, Any]:
    return ensure_store_structure(read_json_file(paths.store_file))


def _make_node_record(
    normalized: dict[str, Any],
    *,
    origin_kind: str,
    subscription_id: str | None = None,
    name: str | None = None,
    raw_uri: str | None = None,
) -> dict[str, Any]:
    now = iso_now()
    fingerprint_hash = normalized.get("fingerprint_hash")
    if not fingerprint_hash:
        payload = {
            key: value
            for key, value in normalized.items()
            if key not in {"display_name", "raw_uri", "origin_uri"}
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return {
        "id": f"node-{uuid4().hex}",
        "fingerprint": fingerprint_hash,
        "name": name or normalized["display_name"],
        "protocol": normalized["protocol"],
        "raw_uri": raw_uri if raw_uri is not None else normalized.get("raw_uri", ""),
        "origin": {
            "kind": origin_kind,
            "subscription_id": subscription_id,
        },
        "enabled": True,
        "user_renamed": False,
        "parse_error": "",
        "normalized": normalized,
        "created_at": now,
        "updated_at": now,
    }


def _find_profile(store: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
    for profile in store["profiles"]:
        if profile.get("id") == profile_id:
            return profile
    return None


def _find_subscription(store: dict[str, Any], subscription_id: str) -> dict[str, Any] | None:
    for subscription in store["subscriptions"]:
        if subscription.get("id") == subscription_id:
            return subscription
    return None


def _find_node(store: dict[str, Any], profile_id: str, node_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = _find_profile(store, profile_id)
    if not profile:
        return None, None
    for node in profile["nodes"]:
        if node.get("id") == node_id:
            return profile, node
    return profile, None


def get_active_node(store: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    selection = store.get("active_selection", {})
    profile_id = selection.get("profile_id")
    node_id = selection.get("node_id")
    if not profile_id or not node_id:
        return None, None
    return _find_node(store, profile_id, node_id)


def _find_routing_profile(store: dict[str, Any], profile_id: str | None) -> dict[str, Any] | None:
    if not profile_id:
        return None
    for profile in store.get("routing", {}).get("profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return None


def _find_routing_profile_by_name(store: dict[str, Any], name_key: str) -> dict[str, Any] | None:
    for profile in store.get("routing", {}).get("profiles", []):
        if profile.get("name_key") == name_key:
            return profile
    return None


def get_active_routing_profile(store: dict[str, Any]) -> dict[str, Any] | None:
    return _find_routing_profile(store, store.get("routing", {}).get("active_profile_id"))


def _routing_geodata_for_profile(
    paths: AppPaths,
    routing: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    geoip_url = str(profile.get("geoip_url") or "")
    geosite_url = str(profile.get("geosite_url") or "")
    previous = routing.get("geodata") or {}
    same_urls = previous.get("geoip_url") == geoip_url and previous.get("geosite_url") == geosite_url

    if same_urls:
        status = get_existing_geodata_status(paths, geoip_url=geoip_url, geosite_url=geosite_url)
        if previous.get("status") == "error" and not status["ready"]:
            status["status"] = "error"
            status["error"] = str(previous.get("error") or "")
        return status

    return build_geodata_status(
        paths,
        geoip_url=geoip_url,
        geosite_url=geosite_url,
        status="missing",
        error="",
    )


def ensure_routing_state(store: dict[str, Any], paths: AppPaths) -> bool:
    routing = store.setdefault("routing", default_store()["routing"])
    before = json.dumps(routing, ensure_ascii=False, sort_keys=True)
    active_profile = get_active_routing_profile(store)

    if not active_profile:
        routing["active_profile_id"] = None
        routing["enabled"] = False
        routing["runtime_ready"] = False
        routing["runtime_error"] = "Активный routing-профиль не выбран."
        routing["geodata"] = {
            **default_routing_geodata_state(),
            "asset_dir": str(paths.xray_asset_dir),
            "geoip_path": str(paths.geoip_asset_file),
            "geosite_path": str(paths.geosite_asset_file),
        }
        return before != json.dumps(routing, ensure_ascii=False, sort_keys=True)

    if not active_profile.get("enabled", True):
        routing["active_profile_id"] = None
        routing["enabled"] = False
        routing["runtime_ready"] = False
        routing["runtime_error"] = f"Routing-профиль '{active_profile.get('name', 'без имени')}' отключён."
        routing["geodata"] = {
            **default_routing_geodata_state(),
            "asset_dir": str(paths.xray_asset_dir),
            "geoip_path": str(paths.geoip_asset_file),
            "geosite_path": str(paths.geosite_asset_file),
        }
        return before != json.dumps(routing, ensure_ascii=False, sort_keys=True)

    routing["geodata"] = _routing_geodata_for_profile(paths, routing, active_profile)
    if routing.get("enabled"):
        if routing["geodata"].get("ready"):
            routing["runtime_ready"] = True
            routing["runtime_error"] = ""
        else:
            routing["runtime_ready"] = False
            routing["runtime_error"] = routing["geodata"].get("error") or "Для маршрутизации не подготовлены geodata-файлы."
    else:
        routing["runtime_ready"] = bool(routing["geodata"].get("ready"))
        routing["runtime_error"] = str(routing["geodata"].get("error") or "")

    return before != json.dumps(routing, ensure_ascii=False, sort_keys=True)


def prepare_routing_runtime(
    store: dict[str, Any],
    paths: AppPaths,
    *,
    uid: int | None = None,
    gid: int | None = None,
    allow_download: bool = False,
) -> dict[str, Any]:
    ensure_routing_state(store, paths)
    routing = store["routing"]
    active_profile = get_active_routing_profile(store)
    if not active_profile:
        return routing["geodata"]
    if routing["geodata"].get("ready") or not allow_download:
        return routing["geodata"]

    try:
        routing["geodata"] = download_routing_geodata(paths, active_profile, uid=uid, gid=gid)
        ensure_routing_state(store, paths)
    except RoutingProfileError as exc:
        routing["geodata"] = build_geodata_status(
            paths,
            geoip_url=str(active_profile.get("geoip_url") or ""),
            geosite_url=str(active_profile.get("geosite_url") or ""),
            status="error",
            error=str(exc),
        )
        routing["runtime_ready"] = False
        routing["runtime_error"] = str(exc)
    return routing["geodata"]


def ensure_active_selection(store: dict[str, Any]) -> bool:
    selection = store["active_selection"]
    active_profile, active_node = get_active_node(store)
    if (
        active_profile
        and active_node
        and active_profile.get("enabled", True)
        and node_can_render_runtime(active_node)
    ):
        return False

    if any(selection.get(key) for key in ("profile_id", "node_id", "activated_at", "source")):
        store["active_selection"] = {
            "profile_id": None,
            "node_id": None,
            "activated_at": None,
            "source": None,
        }
        return True

    return False


def sync_generated_runtime(
    store: dict[str, Any],
    paths: AppPaths,
    project_root: Path,
    uid: int | None = None,
    gid: int | None = None,
) -> Path | None:
    ensure_routing_state(store, paths)
    active_profile, active_node = get_active_node(store)
    if not active_profile or not active_node or not active_profile.get("enabled", True) or not node_can_render_runtime(active_node):
        remove_file_if_exists(paths.generated_xray_config_file)
        return None

    routing_profile = None
    routing = store.get("routing", {})
    if routing.get("enabled"):
        if not routing.get("runtime_ready"):
            remove_file_if_exists(paths.generated_xray_config_file)
            return None
        routing_profile = get_active_routing_profile(store)
        if not routing_profile:
            remove_file_if_exists(paths.generated_xray_config_file)
            return None

    template_config = read_json_config(project_root / "xray-tun-subvost.json")
    rendered = render_runtime_config(template_config, active_node, routing_profile=routing_profile)
    atomic_write_json(paths.generated_xray_config_file, rendered, uid=uid, gid=gid)
    return paths.generated_xray_config_file


def ensure_store_initialized(
    paths: AppPaths,
    project_root: Path,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    ensure_store_dir(paths, uid=uid, gid=gid)
    raw_store = read_json_file(paths.store_file)
    store = ensure_store_structure(raw_store)
    changed = raw_store != store
    if ensure_active_selection(store):
        changed = True
    if ensure_routing_state(store, paths):
        changed = True
    if changed or not paths.store_file.exists():
        save_store(paths, store, uid=uid, gid=gid)
    sync_generated_runtime(store, paths, project_root, uid=uid, gid=gid)
    return store


def store_summary(store: dict[str, Any]) -> dict[str, int]:
    total_nodes = sum(len(profile["nodes"]) for profile in store["profiles"])
    enabled_nodes = sum(
        1 for profile in store["profiles"] for node in profile["nodes"] if profile.get("enabled", True) and node.get("enabled", True)
    )
    return {
        "profiles_total": len(store["profiles"]),
        "subscriptions_total": len(store["subscriptions"]),
        "nodes_total": total_nodes,
        "nodes_enabled": enabled_nodes,
        "routing_profiles_total": len(store.get("routing", {}).get("profiles", [])),
    }


def store_payload(store: dict[str, Any], paths: AppPaths) -> dict[str, Any]:
    active_profile, active_node = get_active_node(store)
    active_routing_profile = get_active_routing_profile(store)
    return {
        "store": store,
        "summary": store_summary(store),
        "active_profile": active_profile,
        "active_node": active_node,
        "active_routing_profile": active_routing_profile,
        "paths": {
            "store_file": str(paths.store_file),
            "generated_xray_config": str(paths.generated_xray_config_file),
            "active_runtime_xray_config": str(paths.active_runtime_xray_config_file),
            "gui_settings_file": str(paths.gui_settings_file),
            "xray_asset_dir": str(paths.xray_asset_dir),
            "geoip_asset_file": str(paths.geoip_asset_file),
            "geosite_asset_file": str(paths.geosite_asset_file),
        },
    }


def save_manual_import_results(
    store: dict[str, Any],
    previews: list[dict[str, Any]],
    *,
    activate_single: bool = False,
) -> dict[str, Any]:
    profile = _find_profile(store, MANUAL_PROFILE_ID)
    if not profile:
        raise ValueError("Не найден ручной профиль импорта.")

    fingerprint_to_node = {node["fingerprint"]: node for node in profile["nodes"]}
    created = 0
    updated = 0
    candidate_node_id: str | None = None
    valid_results = [item for item in previews if item.get("valid")]
    for result in valid_results:
        normalized = result["normalized"]
        existing = fingerprint_to_node.get(result["fingerprint"])
        if existing:
            existing["raw_uri"] = result["raw_uri"]
            existing["normalized"] = normalized
            existing["protocol"] = normalized["protocol"]
            if not existing.get("user_renamed"):
                existing["name"] = normalized["display_name"]
            existing["updated_at"] = iso_now()
            updated += 1
            candidate_node_id = existing["id"]
            continue

        new_node = _make_node_record(normalized, origin_kind="manual", raw_uri=result["raw_uri"])
        profile["nodes"].append(new_node)
        fingerprint_to_node[new_node["fingerprint"]] = new_node
        created += 1
        candidate_node_id = new_node["id"]

    if activate_single and len(valid_results) == 1 and candidate_node_id:
        store["active_selection"] = {
            "profile_id": MANUAL_PROFILE_ID,
            "node_id": candidate_node_id,
            "activated_at": iso_now(),
            "source": "manual_import",
        }

    ensure_active_selection(store)
    return {
        "created": created,
        "updated": updated,
        "valid": len(valid_results),
        "invalid": len(previews) - len(valid_results),
    }


def import_routing_profile(
    store: dict[str, Any],
    paths: AppPaths,
    raw_text: str,
    *,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    parsed = parse_routing_profile_input(raw_text)
    now = iso_now()
    routing = store["routing"]
    existing = _find_routing_profile_by_name(store, parsed["name_key"])

    if existing:
        profile = _normalize_routing_profile(
            {
                **existing,
                **parsed,
                "id": existing["id"],
                "enabled": existing.get("enabled", True),
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
        )
        routing["profiles"] = [
            profile if item.get("id") == existing["id"] else item
            for item in routing["profiles"]
        ]
        created = False
    else:
        profile = _normalize_routing_profile(
            {
                **parsed,
                "id": f"routing-{uuid4().hex}",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        routing["profiles"].append(profile)
        created = True

    if not routing.get("active_profile_id"):
        routing["active_profile_id"] = profile["id"]

    allow_download = routing.get("active_profile_id") == profile["id"]
    geodata = prepare_routing_runtime(store, paths, uid=uid, gid=gid, allow_download=allow_download)
    ensure_routing_state(store, paths)
    return {
        "created": created,
        "profile": profile,
        "geodata": geodata,
    }


def activate_routing_profile(
    store: dict[str, Any],
    paths: AppPaths,
    profile_id: str,
    *,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    profile = _find_routing_profile(store, profile_id)
    if not profile:
        raise ValueError("Routing-профиль не найден.")
    if not profile.get("enabled", True):
        raise ValueError("Routing-профиль отключён.")

    routing = store["routing"]
    previous_active_id = routing.get("active_profile_id")
    previous_geodata = copy.deepcopy(routing.get("geodata") or {})
    previous_runtime_ready = bool(routing.get("runtime_ready"))
    previous_runtime_error = str(routing.get("runtime_error") or "")

    routing["active_profile_id"] = profile_id
    geodata = prepare_routing_runtime(store, paths, uid=uid, gid=gid, allow_download=True)
    if routing.get("enabled") and not geodata.get("ready"):
        routing["active_profile_id"] = previous_active_id
        routing["geodata"] = previous_geodata
        routing["runtime_ready"] = previous_runtime_ready
        routing["runtime_error"] = previous_runtime_error
        ensure_routing_state(store, paths)
        raise ValueError(geodata.get("error") or "Не удалось подготовить geodata для выбранного routing-профиля.")

    ensure_routing_state(store, paths)
    return profile


def clear_active_routing_profile(store: dict[str, Any], paths: AppPaths) -> None:
    store["routing"]["active_profile_id"] = None
    store["routing"]["enabled"] = False
    ensure_routing_state(store, paths)


def update_routing_profile_enabled(
    store: dict[str, Any],
    paths: AppPaths,
    profile_id: str,
    *,
    enabled: bool,
) -> dict[str, Any]:
    profile = _find_routing_profile(store, profile_id)
    if not profile:
        raise ValueError("Routing-профиль не найден.")

    profile["enabled"] = bool(enabled)
    profile["updated_at"] = iso_now()
    if not profile["enabled"] and store["routing"].get("active_profile_id") == profile_id:
        store["routing"]["active_profile_id"] = None
        store["routing"]["enabled"] = False
    ensure_routing_state(store, paths)
    return profile


def set_routing_enabled(
    store: dict[str, Any],
    paths: AppPaths,
    enabled: bool,
    *,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    routing = store["routing"]
    if not enabled:
        routing["enabled"] = False
        ensure_routing_state(store, paths)
        return routing

    active_profile = get_active_routing_profile(store)
    if not active_profile:
        raise ValueError("Сначала выбери routing-профиль.")
    if not active_profile.get("enabled", True):
        raise ValueError("Активный routing-профиль отключён.")

    geodata = prepare_routing_runtime(store, paths, uid=uid, gid=gid, allow_download=True)
    if not geodata.get("ready"):
        raise ValueError(geodata.get("error") or "Не удалось подготовить geodata для маршрутизации.")

    routing["enabled"] = True
    ensure_routing_state(store, paths)
    return routing


def activate_selection(store: dict[str, Any], profile_id: str, node_id: str, source: str = "ui") -> dict[str, Any]:
    profile, node = _find_node(store, profile_id, node_id)
    if not profile or not node:
        raise ValueError("Узел для активации не найден.")
    if not profile.get("enabled", True):
        raise ValueError("Профиль отключён и не может быть активирован.")
    if not node.get("enabled", True):
        raise ValueError("Узел отключён и не может быть активирован.")
    store["active_selection"] = {
        "profile_id": profile_id,
        "node_id": node_id,
        "activated_at": iso_now(),
        "source": source,
    }
    return node


def update_profile(store: dict[str, Any], profile_id: str, *, name: str | None = None, enabled: bool | None = None) -> dict[str, Any]:
    profile = _find_profile(store, profile_id)
    if not profile:
        raise ValueError("Профиль не найден.")
    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("Имя профиля не может быть пустым.")
        profile["name"] = new_name
    if enabled is not None:
        if profile["id"] == MANUAL_PROFILE_ID:
            raise ValueError("Базовый ручной профиль нельзя отключить.")
        profile["enabled"] = bool(enabled)

    subscription_id = profile.get("source_subscription_id")
    if subscription_id:
        subscription = _find_subscription(store, subscription_id)
        if subscription:
            if name is not None:
                subscription["name"] = profile["name"]
            if enabled is not None:
                subscription["enabled"] = profile["enabled"]
    ensure_active_selection(store)
    return profile


def delete_profile(store: dict[str, Any], profile_id: str) -> None:
    if profile_id == MANUAL_PROFILE_ID:
        raise ValueError("Базовый ручной профиль нельзя удалить.")
    profile = _find_profile(store, profile_id)
    if not profile:
        raise ValueError("Профиль не найден.")

    subscription_id = profile.get("source_subscription_id")
    store["profiles"] = [item for item in store["profiles"] if item.get("id") != profile_id]
    if subscription_id:
        store["subscriptions"] = [item for item in store["subscriptions"] if item.get("id") != subscription_id]
    ensure_active_selection(store)


def update_node(
    store: dict[str, Any],
    profile_id: str,
    node_id: str,
    *,
    name: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    profile, node = _find_node(store, profile_id, node_id)
    if not profile or not node:
        raise ValueError("Узел не найден.")
    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("Имя узла не может быть пустым.")
        node["name"] = new_name
        node["user_renamed"] = True
    if enabled is not None:
        node["enabled"] = bool(enabled)
    node["updated_at"] = iso_now()
    ensure_active_selection(store)
    return node


def delete_node(store: dict[str, Any], profile_id: str, node_id: str) -> None:
    profile = _find_profile(store, profile_id)
    if not profile:
        raise ValueError("Профиль не найден.")
    before_count = len(profile["nodes"])
    profile["nodes"] = [node for node in profile["nodes"] if node.get("id") != node_id]
    if len(profile["nodes"]) == before_count:
        raise ValueError("Узел не найден.")
    ensure_active_selection(store)


def add_subscription(store: dict[str, Any], name: str, url: str) -> dict[str, Any]:
    subscription_name = name.strip()
    subscription_url = url.strip()
    if not subscription_url:
        raise ValueError("URL подписки не может быть пустым.")

    if not subscription_name:
        host = urlsplit(subscription_url).hostname
        subscription_name = host or "Новая подписка"

    subscription_id = f"sub-{uuid4().hex}"
    profile_id = f"profile-{uuid4().hex}"
    profile = {
        "id": profile_id,
        "kind": "subscription",
        "name": subscription_name,
        "enabled": True,
        "source_subscription_id": subscription_id,
        "nodes": [],
    }
    subscription = {
        "id": subscription_id,
        "name": subscription_name,
        "url": subscription_url,
        "enabled": True,
        "etag": "",
        "last_modified": "",
        "last_success_at": None,
        "last_status": "never",
        "last_error": "",
        "profile_id": profile_id,
    }
    store["profiles"].append(profile)
    store["subscriptions"].append(subscription)
    return subscription


def _node_map_by_fingerprint(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["fingerprint"]: node for node in profile["nodes"]}


def _apply_subscription_refresh(
    store: dict[str, Any],
    subscription: dict[str, Any],
    parsed_links: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = _find_profile(store, subscription["profile_id"])
    if not profile:
        raise ValueError("Не найден профиль подписки.")

    existing_nodes = _node_map_by_fingerprint(profile)
    new_nodes: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    valid_count = 0
    invalid_count = 0
    duplicate_count = 0
    invalid_messages: list[str] = []

    for result in parsed_links:
        if not result.get("valid"):
            invalid_count += 1
            if result.get("error"):
                invalid_messages.append(str(result["error"]))
            continue

        valid_count += 1
        normalized = result["normalized"]
        fingerprint = result["fingerprint"]
        existing = existing_nodes.get(fingerprint)
        if existing:
            if fingerprint in seen_fingerprints:
                duplicate_count += 1
                continue

            updated_node = copy.deepcopy(existing)
            updated_node["raw_uri"] = result["raw_uri"]
            updated_node["normalized"] = normalized
            updated_node["protocol"] = normalized["protocol"]
            updated_node["origin"] = {
                "kind": "subscription",
                "subscription_id": subscription["id"],
            }
            if not updated_node.get("user_renamed"):
                updated_node["name"] = normalized["display_name"]
            updated_node["updated_at"] = iso_now()
            new_nodes.append(updated_node)
            seen_fingerprints.add(fingerprint)
            continue

        new_node = _make_node_record(
            normalized,
            origin_kind="subscription",
            subscription_id=subscription["id"],
            raw_uri=result["raw_uri"],
        )
        if fingerprint in seen_fingerprints:
            duplicate_count += 1
            continue
        new_nodes.append(new_node)
        seen_fingerprints.add(fingerprint)

    if valid_count == 0:
        if invalid_messages:
            raise ParseError(invalid_messages[0])
        raise ParseError("В подписке не найдено ни одной валидной ссылки.")
    if invalid_count > 0:
        error_suffix = f" Первая ошибка: {invalid_messages[0]}" if invalid_messages else ""
        raise ParseError(
            f"Обновление подписки не применено: невалидных строк {invalid_count}.{error_suffix}"
        )

    profile["nodes"] = new_nodes
    ensure_active_selection(store)
    return {
        "valid": valid_count,
        "invalid": invalid_count,
        "unique_nodes": len(new_nodes),
        "duplicate_lines": duplicate_count,
        "status": "ok",
    }


def refresh_subscription(store: dict[str, Any], subscription_id: str) -> dict[str, Any]:
    subscription = _find_subscription(store, subscription_id)
    if not subscription:
        raise ValueError("Подписка не найдена.")

    request = urllib.request.Request(subscription["url"])
    request.add_header("User-Agent", DEFAULT_SUBSCRIPTION_USER_AGENT)
    request.add_header("Accept", "text/plain, application/octet-stream, */*")
    request.add_header("X-HWID", default_subscription_hwid())
    request.add_header("X-Device-OS", platform.system() or "Linux")
    request.add_header("X-Ver-OS", platform.release() or "unknown")
    request.add_header("X-Device-Model", platform.machine() or socket.gethostname() or "unknown")
    if subscription.get("etag"):
        request.add_header("If-None-Match", subscription["etag"])
    if subscription.get("last_modified"):
        request.add_header("If-Modified-Since", subscription["last_modified"])

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status_code = getattr(response, "status", 200)
            if status_code == 304:
                subscription["last_status"] = "ok"
                subscription["last_error"] = ""
                subscription["last_success_at"] = iso_now()
                return {
                    "status": "ok",
                    "valid": 0,
                    "invalid": 0,
                    "unique_nodes": len(profile["nodes"]) if (profile := _find_profile(store, subscription["profile_id"])) else 0,
                    "duplicate_lines": 0,
                    "format": "not_modified",
                }

            payload = response.read()
            links, response_format = parse_subscription_payload(payload)
            previews = []
            for line in links:
                try:
                    normalized = parse_proxy_uri(line)
                    previews.append(
                        {
                            "raw_uri": line,
                            "valid": True,
                            "error": "",
                            "fingerprint": normalized["fingerprint_hash"],
                            "normalized": normalized,
                        }
                    )
                except ParseError as exc:
                    previews.append(
                        {
                            "raw_uri": line,
                            "valid": False,
                            "error": str(exc),
                            "fingerprint": "",
                            "normalized": {},
                        }
                    )

            result = _apply_subscription_refresh(store, subscription, previews)
            subscription["etag"] = response.headers.get("ETag", "")
            subscription["last_modified"] = response.headers.get("Last-Modified", "")
            subscription["last_success_at"] = iso_now()
            subscription["last_status"] = result["status"]
            subscription["last_error"] = ""
            return {**result, "format": response_format}
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            subscription["last_status"] = "ok"
            subscription["last_error"] = ""
            subscription["last_success_at"] = iso_now()
            return {
                "status": "ok",
                "valid": 0,
                "invalid": 0,
                "unique_nodes": len(profile["nodes"]) if (profile := _find_profile(store, subscription["profile_id"])) else 0,
                "duplicate_lines": 0,
                "format": "not_modified",
            }
        subscription["last_status"] = "error"
        subscription["last_error"] = f"HTTP {exc.code}"
        raise ValueError(f"Подписка вернула HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        subscription["last_status"] = "error"
        subscription["last_error"] = str(exc.reason)
        raise ValueError(f"Не удалось загрузить подписку: {exc.reason}.") from exc
    except ParseError as exc:
        subscription["last_status"] = "error"
        subscription["last_error"] = str(exc)
        raise ValueError(str(exc)) from exc


def refresh_all_subscriptions(store: dict[str, Any]) -> dict[str, Any]:
    items = []
    ok_count = 0
    error_count = 0
    for subscription in store["subscriptions"]:
        if not subscription.get("enabled", True):
            continue
        try:
            result = refresh_subscription(store, subscription["id"])
            items.append({"id": subscription["id"], "name": subscription["name"], **result})
            ok_count += 1
        except ValueError as exc:
            items.append({"id": subscription["id"], "name": subscription["name"], "status": "error", "message": str(exc)})
            error_count += 1
    return {
        "items": items,
        "ok": ok_count,
        "error": error_count,
    }


def update_subscription(
    store: dict[str, Any],
    subscription_id: str,
    *,
    name: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    subscription = _find_subscription(store, subscription_id)
    if not subscription:
        raise ValueError("Подписка не найдена.")
    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("Имя подписки не может быть пустым.")
        subscription["name"] = new_name
        profile = _find_profile(store, subscription["profile_id"])
        if profile:
            profile["name"] = new_name
    if enabled is not None:
        subscription["enabled"] = bool(enabled)
        profile = _find_profile(store, subscription["profile_id"])
        if profile:
            profile["enabled"] = bool(enabled)
    ensure_active_selection(store)
    return subscription


def delete_subscription(store: dict[str, Any], subscription_id: str) -> None:
    subscription = _find_subscription(store, subscription_id)
    if not subscription:
        raise ValueError("Подписка не найдена.")
    profile_id = subscription["profile_id"]
    store["subscriptions"] = [item for item in store["subscriptions"] if item.get("id") != subscription_id]
    store["profiles"] = [item for item in store["profiles"] if item.get("id") != profile_id]
    ensure_active_selection(store)


def normalize_gui_theme(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"light", "dark"}:
        return candidate
    return "system"


def normalize_gui_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    payload = settings or {}
    return {
        "file_logs_enabled": bool(payload.get("file_logs_enabled", False)),
        "close_to_tray": bool(payload.get("close_to_tray", False)),
        "start_minimized_to_tray": bool(payload.get("start_minimized_to_tray", False)),
        "theme": normalize_gui_theme(payload.get("theme")),
    }


def read_gui_settings(paths: AppPaths, uid: int | None = None, gid: int | None = None) -> dict[str, Any]:
    ensure_store_dir(paths, uid=uid, gid=gid)
    return normalize_gui_settings(read_json_file(paths.gui_settings_file))


def save_gui_settings(
    paths: AppPaths,
    file_logs_enabled: bool | None = None,
    uid: int | None = None,
    gid: int | None = None,
    *,
    close_to_tray: bool | None = None,
    start_minimized_to_tray: bool | None = None,
    theme: str | None = None,
) -> None:
    ensure_store_dir(paths, uid=uid, gid=gid)
    settings = read_gui_settings(paths, uid=uid, gid=gid)
    if file_logs_enabled is not None:
        settings["file_logs_enabled"] = bool(file_logs_enabled)
    if close_to_tray is not None:
        settings["close_to_tray"] = bool(close_to_tray)
    if start_minimized_to_tray is not None:
        settings["start_minimized_to_tray"] = bool(start_minimized_to_tray)
    if theme is not None:
        settings["theme"] = normalize_gui_theme(theme)
    atomic_write_json(paths.gui_settings_file, settings, uid=uid, gid=gid)
