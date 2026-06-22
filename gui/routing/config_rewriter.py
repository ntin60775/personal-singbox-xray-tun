from __future__ import annotations

import copy
from typing import Any

from .profile_manager import _split_template_rules


def _build_profile_rule(profile: dict[str, Any], prefix: str, outbound_tag: str) -> dict[str, Any] | None:
    """Строит одно Xray routing-правило из полей профиля по префиксу политики.

    Собирает домены из `{prefix}_sites` и IP из `{prefix}_ip` профиля. Если оба
    списка пусты — возвращает `None` (правило не создаётся).

    Args:
        profile: нормализованный dict профиля маршрутизации.
        prefix: префикс политики — один из `"block"`, `"direct"`, `"proxy"`.
        outbound_tag: тег outbound'а в Xray-конфиге (`"block"`, `"direct"`, `"proxy"`).

    Инвариант: `profile` не мутируется; списки копируются через `copy.deepcopy`.
    """
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
    """Применяет профиль маршрутизации к Xray-конфигу.

    Алгоритм:
      1. Извлекает базовые правила шаблона и catch-all через `_split_template_rules`.
      2. Строит правила из профиля в порядке `route_order` (block → direct → proxy).
      3. Назначает `outboundTag` catch-all в зависимости от `global_proxy`.
      4. Устанавливает `domainStrategy` из профиля (или `"AsIs"` по умолчанию).
      5. Собирает итоговый `routing.rules` как: `базовые + профильные + catch-all`.

    Returns:
        Новый словарь Xray-конфига (deep copy) — исходный `config` не мутируется.

    Инвариант: чистая функция — нет побочных эффектов, не пишет на диск, не сетится.
    """
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
