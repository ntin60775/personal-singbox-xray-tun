from __future__ import annotations

import copy
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from subvost_parser import ParseError, parse_proxy_uri, parse_subscription_payload
from subvost_paths import AppPaths, atomic_write_json, ensure_store_dir, read_json_file, remove_file_if_exists
from subvost_runtime import config_has_placeholders, extract_node_from_existing_config, node_can_render_runtime, read_json_config, render_runtime_config


STORE_VERSION = 1
MANUAL_PROFILE_ID = "manual"
MANUAL_PROFILE_NAME = "Локальные ссылки"
RUNTIME_PREFERENCE_STORE = "store"
RUNTIME_PREFERENCE_BUILTIN = "builtin"
VALID_RUNTIME_PREFERENCES = {RUNTIME_PREFERENCE_STORE, RUNTIME_PREFERENCE_BUILTIN}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def default_store() -> dict[str, Any]:
    return {
        "version": STORE_VERSION,
        "runtime_preference": RUNTIME_PREFERENCE_STORE,
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
        "meta": {
            "initialized_at": iso_now(),
            "migrated_from_single_config_at": None,
        },
    }


def ensure_store_structure(store: dict[str, Any]) -> dict[str, Any]:
    if not store:
        store = default_store()
    store.setdefault("version", STORE_VERSION)
    store.setdefault("runtime_preference", RUNTIME_PREFERENCE_STORE)
    store.setdefault("profiles", [])
    store.setdefault("subscriptions", [])
    store.setdefault(
        "active_selection",
        {"profile_id": None, "node_id": None, "activated_at": None, "source": None},
    )
    store.setdefault("meta", {})
    store["meta"].setdefault("initialized_at", iso_now())
    store["meta"].setdefault("migrated_from_single_config_at", None)
    if store.get("runtime_preference") not in VALID_RUNTIME_PREFERENCES:
        store["runtime_preference"] = RUNTIME_PREFERENCE_STORE
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


def _first_available_node(store: dict[str, Any], preferred_profile_id: str | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profiles = store["profiles"]
    if preferred_profile_id:
        preferred_profile = _find_profile(store, preferred_profile_id)
        if preferred_profile:
            profiles = [preferred_profile] + [profile for profile in profiles if profile.get("id") != preferred_profile_id]

    for profile in profiles:
        if not profile.get("enabled", True):
            continue
        for node in profile["nodes"]:
            if node.get("enabled", True) and not node.get("parse_error"):
                return profile, node
    return None, None


def ensure_active_selection(store: dict[str, Any]) -> bool:
    changed = False
    selection = store["active_selection"]
    active_profile, active_node = get_active_node(store)
    if active_profile and active_node and active_profile.get("enabled", True) and active_node.get("enabled", True):
        return False

    preferred_profile_id = selection.get("profile_id")
    fallback_profile, fallback_node = _first_available_node(store, preferred_profile_id)
    if fallback_profile and fallback_node:
        store["active_selection"] = {
            "profile_id": fallback_profile["id"],
            "node_id": fallback_node["id"],
            "activated_at": iso_now(),
            "source": "fallback",
        }
        changed = True
    elif any(selection.get(key) for key in ("profile_id", "node_id", "activated_at", "source")):
        store["active_selection"] = {
            "profile_id": None,
            "node_id": None,
            "activated_at": None,
            "source": None,
        }
        changed = True
    return changed


def sync_generated_runtime(
    store: dict[str, Any],
    paths: AppPaths,
    project_root: Path,
    uid: int | None = None,
    gid: int | None = None,
) -> Path | None:
    active_profile, active_node = get_active_node(store)
    if not active_profile or not active_node or not active_profile.get("enabled", True) or not node_can_render_runtime(active_node):
        remove_file_if_exists(paths.generated_xray_config_file)
        return None

    template_config = read_json_config(project_root / "xray-tun-subvost.json")
    rendered = render_runtime_config(template_config, active_node)
    atomic_write_json(paths.generated_xray_config_file, rendered, uid=uid, gid=gid)
    return paths.generated_xray_config_file


def _should_migrate_single_config(store: dict[str, Any]) -> bool:
    manual_profile = _find_profile(store, MANUAL_PROFILE_ID)
    if manual_profile and manual_profile["nodes"]:
        return False
    if store.get("subscriptions"):
        return False
    selection = store.get("active_selection", {})
    return not selection.get("profile_id") and not selection.get("node_id")


def maybe_migrate_single_config(
    store: dict[str, Any],
    project_root: Path,
) -> bool:
    if not _should_migrate_single_config(store):
        return False

    config = read_json_config(project_root / "xray-tun-subvost.json")
    if not config or config_has_placeholders(config):
        return False

    normalized = extract_node_from_existing_config(config)
    if not normalized:
        return False

    manual_profile = _find_profile(store, MANUAL_PROFILE_ID)
    if not manual_profile:
        return False

    node = _make_node_record(
        normalized,
        origin_kind="migration",
        name="Migrated from current config",
        raw_uri="",
    )
    manual_profile["nodes"].append(node)
    store["active_selection"] = {
        "profile_id": MANUAL_PROFILE_ID,
        "node_id": node["id"],
        "activated_at": iso_now(),
        "source": "migration",
    }
    store["meta"]["migrated_from_single_config_at"] = iso_now()
    return True


def ensure_store_initialized(
    paths: AppPaths,
    project_root: Path,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    ensure_store_dir(paths, uid=uid, gid=gid)
    store = load_store(paths)
    changed = False
    if maybe_migrate_single_config(store, project_root):
        changed = True
    if ensure_active_selection(store):
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
    }


def store_payload(store: dict[str, Any], paths: AppPaths) -> dict[str, Any]:
    active_profile, active_node = get_active_node(store)
    return {
        "store": store,
        "summary": store_summary(store),
        "active_profile": active_profile,
        "active_node": active_node,
        "paths": {
            "store_file": str(paths.store_file),
            "generated_xray_config": str(paths.generated_xray_config_file),
            "active_runtime_xray_config": str(paths.active_runtime_xray_config_file),
            "gui_settings_file": str(paths.gui_settings_file),
        },
    }


def get_runtime_preference(store: dict[str, Any]) -> str:
    preference = str(store.get("runtime_preference", "")).strip().lower()
    if preference in VALID_RUNTIME_PREFERENCES:
        return preference
    return RUNTIME_PREFERENCE_STORE


def set_runtime_preference(store: dict[str, Any], preference: str) -> str:
    normalized = str(preference or "").strip().lower()
    if normalized not in VALID_RUNTIME_PREFERENCES:
        raise ValueError("Источник runtime должен быть 'store' или 'builtin'.")
    store["runtime_preference"] = normalized
    return normalized


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


def read_or_migrate_gui_settings(paths: AppPaths, uid: int | None = None, gid: int | None = None) -> dict[str, Any]:
    ensure_store_dir(paths, uid=uid, gid=gid)
    if not paths.gui_settings_file.exists() and paths.legacy_gui_settings_file.exists():
        legacy_settings = read_json_file(paths.legacy_gui_settings_file)
        if legacy_settings:
            atomic_write_json(paths.gui_settings_file, legacy_settings, uid=uid, gid=gid)

    settings = read_json_file(paths.gui_settings_file)
    return {
        "file_logs_enabled": bool(settings.get("file_logs_enabled", False)),
    }


def save_gui_settings(paths: AppPaths, file_logs_enabled: bool, uid: int | None = None, gid: int | None = None) -> None:
    ensure_store_dir(paths, uid=uid, gid=gid)
    atomic_write_json(paths.gui_settings_file, {"file_logs_enabled": bool(file_logs_enabled)}, uid=uid, gid=gid)
