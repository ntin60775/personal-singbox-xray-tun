from __future__ import annotations

import base64
import copy
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from subvost_paths import AppPaths, atomic_write_bytes, ensure_owned_dir


DEFAULT_GEOIP_URL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
DEFAULT_GEOSITE_URL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"
SUPPORTED_DOMAIN_STRATEGIES = {"AsIs", "IPIfNonMatch", "IPOnDemand", "UseIP"}
ROUTING_URI_PREFIXES = ("happ://routing/add/", "happ://routing/onadd/")
ROUTING_URI_ACTIVATION_MODE = {
    "happ://routing/add/": "add",
    "happ://routing/onadd/": "onadd",
}
STORED_ONLY_FIELDS = {
    "dns_hosts",
    "domestic_dns_domain",
    "domestic_dns_ip",
    "domestic_dns_type",
    "remote_dns_domain",
    "remote_dns_ip",
    "remote_dns_type",
    "fake_dns",
    "last_updated",
}
KNOWN_IMPORT_KEYS = {
    "name",
    "globalproxy",
    "domainstrategy",
    "geoipurl",
    "geositeurl",
    "directsites",
    "directip",
    "proxysites",
    "proxyip",
    "blocksites",
    "blockip",
    "dnshosts",
    "domesticdnsdomain",
    "domesticdnsip",
    "domesticdnstype",
    "remotednsdomain",
    "remotednsip",
    "remotednstype",
    "fakedns",
    "routeorder",
    "lastupdated",
}


class RoutingProfileError(ValueError):
    pass


def _decode_base64(value: str) -> bytes:
    cleaned = "".join(value.strip().split())
    padding = "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((cleaned + padding).encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RoutingProfileError("Не удалось декодировать base64 routing-профиля.") from exc


def _decode_base64_json(value: str) -> dict[str, Any]:
    try:
        decoded = _decode_base64(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoutingProfileError("Base64 routing-профиля не является UTF-8 JSON.") from exc
    return _parse_json_payload(decoded)


def _parse_json_payload(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RoutingProfileError("Routing-профиль должен быть валидным JSON-объектом.") from exc
    if not isinstance(payload, dict):
        raise RoutingProfileError("Routing-профиль должен быть JSON-объектом.")
    return payload


def _extract_happ_routing_payload(text: str) -> tuple[dict[str, Any], str, str]:
    stripped = text.strip()
    for prefix in ROUTING_URI_PREFIXES:
        if stripped.startswith(prefix):
            return _decode_base64_json(stripped[len(prefix) :]), "happ_uri", ROUTING_URI_ACTIVATION_MODE[prefix]

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    happ_lines = [line for line in lines if any(line.startswith(prefix) for prefix in ROUTING_URI_PREFIXES)]
    if len(happ_lines) == 1:
        return _extract_happ_routing_payload(happ_lines[0])
    raise RoutingProfileError("В тексте не найден поддерживаемый `happ://routing/...` URI.")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                result.append(cleaned)
    return result


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            continue
        cleaned_key = key.strip()
        cleaned_value = item.strip()
        if cleaned_key and cleaned_value:
            result[cleaned_key] = cleaned_value
    return result


def _normalized_name(value: Any) -> str:
    return str(value or "").strip()


def _normalize_domain_strategy(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in SUPPORTED_DOMAIN_STRATEGIES:
        return raw
    return "AsIs"


def _normalize_route_order(value: Any) -> list[str]:
    parts = [part.strip().lower() for part in re.split(r"[^a-z]+", str(value or "").strip()) if part.strip()]
    allowed = {"block", "direct", "proxy"}
    ordered = [part for part in parts if part in allowed]
    if len(set(ordered)) == 3:
        return ordered
    return ["block", "direct", "proxy"]


def _payload_key_map(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip().lower(): value for key, value in payload.items()}


def parse_routing_profile_input(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise RoutingProfileError("Текст routing-профиля пуст.")

    source_format = "json"
    activation_mode = "manual"
    if any(text.startswith(prefix) for prefix in ROUTING_URI_PREFIXES) or "happ://routing/" in text:
        payload, source_format, activation_mode = _extract_happ_routing_payload(text)
    else:
        try:
            payload = _parse_json_payload(text)
        except RoutingProfileError:
            payload = _decode_base64_json(text)
            source_format = "base64_json"

    key_map = _payload_key_map(payload)
    name = _normalized_name(key_map.get("name") or payload.get("Name"))
    if not name:
        raise RoutingProfileError("Routing-профиль должен содержать непустое поле `name`.")

    direct_sites = _string_list(key_map.get("directsites"))
    direct_ip = _string_list(key_map.get("directip"))
    proxy_sites = _string_list(key_map.get("proxysites"))
    proxy_ip = _string_list(key_map.get("proxyip"))
    block_sites = _string_list(key_map.get("blocksites"))
    block_ip = _string_list(key_map.get("blockip"))

    supported_entries = sum(
        len(items)
        for items in [direct_sites, direct_ip, proxy_sites, proxy_ip, block_sites, block_ip]
    )
    unknown_fields = sorted(key for key in key_map if key not in KNOWN_IMPORT_KEYS)
    stored_only_presence = {
        "dns_hosts": "dnshosts" in key_map,
        "domestic_dns_domain": "domesticdnsdomain" in key_map,
        "domestic_dns_ip": "domesticdnsip" in key_map,
        "domestic_dns_type": "domesticdnstype" in key_map,
        "remote_dns_domain": "remotednsdomain" in key_map,
        "remote_dns_ip": "remotednsip" in key_map,
        "remote_dns_type": "remotednstype" in key_map,
        "fake_dns": "fakedns" in key_map,
        "last_updated": "lastupdated" in key_map,
    }

    return {
        "name": name,
        "name_key": name.casefold(),
        "source_format": source_format,
        "activation_mode": activation_mode,
        "raw_payload": payload,
        "global_proxy": _coerce_bool(key_map.get("globalproxy")),
        "domain_strategy": _normalize_domain_strategy(key_map.get("domainstrategy")),
        "geoip_url": str(key_map.get("geoipurl") or DEFAULT_GEOIP_URL).strip() or DEFAULT_GEOIP_URL,
        "geosite_url": str(key_map.get("geositeurl") or DEFAULT_GEOSITE_URL).strip() or DEFAULT_GEOSITE_URL,
        "direct_sites": direct_sites,
        "direct_ip": direct_ip,
        "proxy_sites": proxy_sites,
        "proxy_ip": proxy_ip,
        "block_sites": block_sites,
        "block_ip": block_ip,
        "dns_hosts": _string_map(key_map.get("dnshosts")),
        "domestic_dns_domain": str(key_map.get("domesticdnsdomain") or "").strip(),
        "domestic_dns_ip": str(key_map.get("domesticdnsip") or "").strip(),
        "domestic_dns_type": str(key_map.get("domesticdnstype") or "").strip(),
        "remote_dns_domain": str(key_map.get("remotednsdomain") or "").strip(),
        "remote_dns_ip": str(key_map.get("remotednsip") or "").strip(),
        "remote_dns_type": str(key_map.get("remotednstype") or "").strip(),
        "fake_dns": _coerce_bool(key_map.get("fakedns")),
        "route_order": _normalize_route_order(key_map.get("routeorder")),
        "last_updated": str(key_map.get("lastupdated") or "").strip(),
        "supported_entry_count": supported_entries,
        "stored_only_fields": sorted(field for field, present in stored_only_presence.items() if present and field in STORED_ONLY_FIELDS),
        "ignored_fields": [],
        "unknown_fields": unknown_fields,
    }


def _is_url_candidate(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def download_routing_geodata(
    paths: AppPaths,
    profile: dict[str, Any],
    *,
    uid: int | None = None,
    gid: int | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    geoip_url = str(profile.get("geoip_url") or DEFAULT_GEOIP_URL).strip() or DEFAULT_GEOIP_URL
    geosite_url = str(profile.get("geosite_url") or DEFAULT_GEOSITE_URL).strip() or DEFAULT_GEOSITE_URL

    if not _is_url_candidate(geoip_url):
        raise RoutingProfileError(f"Некорректный URL `geoip.dat`: {geoip_url}")
    if not _is_url_candidate(geosite_url):
        raise RoutingProfileError(f"Некорректный URL `geosite.dat`: {geosite_url}")

    ensure_owned_dir(paths.xray_asset_dir, uid=uid, gid=gid, mode=0o700)
    headers = {"User-Agent": "Subvost-Xray-Tun/1.0", "Accept": "*/*"}

    def fetch(url: str, label: str) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            raise RoutingProfileError(f"Не удалось скачать {label}: HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise RoutingProfileError(f"Не удалось скачать {label}: {exc.reason}.") from exc
        if not payload:
            raise RoutingProfileError(f"{label} скачан пустым файлом.")
        return payload

    geoip_bytes = fetch(geoip_url, "geoip.dat")
    geosite_bytes = fetch(geosite_url, "geosite.dat")
    atomic_write_bytes(paths.geoip_asset_file, geoip_bytes, uid=uid, gid=gid)
    atomic_write_bytes(paths.geosite_asset_file, geosite_bytes, uid=uid, gid=gid)
    return build_geodata_status(
        paths,
        geoip_url=geoip_url,
        geosite_url=geosite_url,
        status="ready",
        error="",
    )


def build_geodata_status(
    paths: AppPaths,
    *,
    geoip_url: str,
    geosite_url: str,
    status: str,
    error: str,
) -> dict[str, Any]:
    geoip_exists = paths.geoip_asset_file.is_file() and paths.geoip_asset_file.stat().st_size > 0 if paths.geoip_asset_file.exists() else False
    geosite_exists = paths.geosite_asset_file.is_file() and paths.geosite_asset_file.stat().st_size > 0 if paths.geosite_asset_file.exists() else False
    ready = status == "ready" and geoip_exists and geosite_exists
    if not ready and status == "ready":
        status = "missing"
    return {
        "status": status,
        "ready": ready,
        "error": error,
        "geoip_url": geoip_url,
        "geosite_url": geosite_url,
        "geoip_path": str(paths.geoip_asset_file),
        "geosite_path": str(paths.geosite_asset_file),
        "asset_dir": str(paths.xray_asset_dir),
        "geoip_exists": geoip_exists,
        "geosite_exists": geosite_exists,
    }


def get_existing_geodata_status(
    paths: AppPaths,
    *,
    geoip_url: str,
    geosite_url: str,
) -> dict[str, Any]:
    ready = paths.geoip_asset_file.exists() and paths.geoip_asset_file.stat().st_size > 0
    ready = ready and paths.geosite_asset_file.exists() and paths.geosite_asset_file.stat().st_size > 0
    return build_geodata_status(
        paths,
        geoip_url=geoip_url,
        geosite_url=geosite_url,
        status="ready" if ready else "missing",
        error="",
    )


def routing_profile_rule_count(profile: dict[str, Any]) -> int:
    return sum(
        len(profile.get(key) or [])
        for key in ["direct_sites", "direct_ip", "proxy_sites", "proxy_ip", "block_sites", "block_ip"]
    )


def _is_tun_catchall_rule(rule: dict[str, Any]) -> bool:
    inbound_tag = rule.get("inboundTag")
    if not isinstance(inbound_tag, list) or "tun-in" not in inbound_tag:
        return False
    return str(rule.get("network") or "").strip().lower() == "tcp,udp"


def _split_template_rules(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    rules = list(config.get("routing", {}).get("rules", []) or [])
    for index in range(len(rules) - 1, -1, -1):
        if _is_tun_catchall_rule(rules[index]):
            return [copy.deepcopy(rule) for rule in rules[:index]], copy.deepcopy(rules[index])
    return [copy.deepcopy(rule) for rule in rules], None


def _build_profile_rule(profile: dict[str, Any], prefix: str, outbound_tag: str) -> dict[str, Any] | None:
    domains = copy.deepcopy(profile.get(f"{prefix}_sites") or [])
    ip_values = copy.deepcopy(profile.get(f"{prefix}_ip") or [])
    if not domains and not ip_values:
        return None

    rule: dict[str, Any] = {
        "type": "field",
        "inboundTag": ["tun-in"],
        "outboundTag": outbound_tag,
    }
    if domains:
        rule["domain"] = domains
    if ip_values:
        rule["ip"] = ip_values
    return rule


def apply_routing_profile_to_config(config: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(config)
    routing = copy.deepcopy(updated.get("routing") or {})
    base_rules, template_catchall = _split_template_rules(updated)

    imported_rules: list[dict[str, Any]] = []
    for prefix in profile.get("route_order") or ["block", "direct", "proxy"]:
        outbound_tag = "block" if prefix == "block" else "direct" if prefix == "direct" else "proxy"
        rule = _build_profile_rule(profile, prefix, outbound_tag)
        if rule:
            imported_rules.append(rule)

    catchall = template_catchall or {
        "type": "field",
        "inboundTag": ["tun-in"],
        "network": "tcp,udp",
        "outboundTag": "proxy",
    }
    catchall["outboundTag"] = "proxy" if profile.get("global_proxy", False) else "direct"

    routing["domainStrategy"] = str(profile.get("domain_strategy") or routing.get("domainStrategy") or "AsIs")
    routing["rules"] = base_rules + imported_rules + [catchall]
    updated["routing"] = routing
    return updated
