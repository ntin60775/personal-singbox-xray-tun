from __future__ import annotations

import copy
from typing import Any

from .profile_manager import _split_template_rules


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
