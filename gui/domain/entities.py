"""Доменные сущности — объекты с идентичностью и жизненным циклом."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .value_objects import NodeAddress, ProtocolConfig, TransportHint


@dataclass
class Node:
    """Узел (прокси-сервер) — дочерняя сущность внутри Profile (агрегат)."""
    id: str
    profile_id: str
    name: str
    protocol_config: ProtocolConfig
    fingerprint: str = ""
    raw_uri: str = ""
    enabled: bool = True
    user_renamed: bool = False
    parse_error: str = ""
    transport_hint: TransportHint | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def address(self) -> NodeAddress:
        pc = self.protocol_config
        return NodeAddress(host=pc.address, port=pc.port, transport=pc.network)

    @property
    def protocol(self) -> str:
        return self.protocol_config.protocol

    def is_valid(self) -> bool:
        """Узел считается валидным, если нет ошибки парсинга и адрес не заглушка."""
        if self.parse_error:
            return False
        pc = self.protocol_config
        if pc.address == "0.0.0.0" and pc.port == 1:
            return False
        if pc.uuid and "00000000-0000-0000-0000-000000000000" in pc.uuid:
            return False
        return True

    def matches_fingerprint(self, fp: str) -> bool:
        """Сравнение fingerprint для дедупликации при импорте."""
        return self.fingerprint == fp


@dataclass
class Subscription:
    """Подписка — источник узлов, получаемых по URL."""
    id: str
    url: str
    name: str = ""
    enabled: bool = True
    etag: str = ""
    last_modified: str = ""
    last_success_at: str | None = None
    last_status: str = "never"
    last_error: str = ""
    profile_id: str | None = None
    provider_id: str = ""
    provider_id_source: str = ""
    routing_profile_id: str | None = None
    last_routing_status: str = "never"
    last_routing_error: str = ""

    def has_nodes(self) -> bool:
        """Есть ли связанный профиль (значит, есть узлы)."""
        return self.profile_id is not None

    def is_stale(self, max_age_days: int = 7) -> bool:
        """Устарела ли подписка (нет успешного обновления за N дней)."""
        if self.last_status == "never":
            return True
        if self.last_success_at is None:
            return True
        try:
            dt = datetime.fromisoformat(self.last_success_at)
            return (datetime.now() - dt).days > max_age_days
        except (ValueError, TypeError):
            return True


@dataclass
class Profile:
    """Профиль — агрегат, содержащий узлы. Корень агрегата."""
    id: str
    name: str
    kind: str = "manual"  # "manual" | "subscription"
    enabled: bool = True
    source_subscription_id: str | None = None
    nodes: list[Node] = field(default_factory=list)

    def activate_node(self, node_id: str) -> Node:
        """Активировать узел. Бросает ValueError если узел не из этого профиля."""
        for node in self.nodes:
            if node.id == node_id:
                if not node.enabled:
                    raise ValueError(f"Узел {node_id} отключен")
                if not node.is_valid():
                    raise ValueError(f"Узел {node_id} невалиден: {node.parse_error}")
                return node
        raise ValueError(f"Узел {node_id} не найден в профиле {self.id}")

    def add_node(self, node: Node) -> None:
        """Добавить узел. Узел должен принадлежать этому профилю."""
        if node.profile_id != self.id:
            raise ValueError(
                f"Узел {node.id} принадлежит профилю {node.profile_id}, а не {self.id}"
            )
        # Замена по id или добавление
        for i, existing in enumerate(self.nodes):
            if existing.id == node.id:
                self.nodes[i] = node
                return
        self.nodes.append(node)

    def remove_node(self, node_id: str) -> None:
        """Удалить узел по id."""
        self.nodes = [n for n in self.nodes if n.id != node_id]

    def active_node_count(self) -> int:
        return sum(1 for n in self.nodes if n.enabled and n.is_valid())

    def has_nodes(self) -> bool:
        return len(self.nodes) > 0


@dataclass
class RoutingRule:
    """Одно правило маршрутизации из профиля."""
    id: str = ""
    source: str = ""  # "template" | "profile" | "runtime"
    kind: str = ""  # "domain" | "ip" | "geosite" | "geoip"
    value: str = ""
    action: str = ""  # "direct" | "proxy" | "block"
    priority: int = 0
    active: bool = True
    rule_index: int = 0


@dataclass
class RoutingProfile:
    """Профиль маршрутизации — управляет geoip/geosite и правилами."""
    id: str
    name: str
    name_key: str = ""
    enabled: bool = True
    auto_managed: bool = False
    source_kind: str = "manual_import"  # "subscription" | "manual_import"
    source_format: str = "json"
    activation_mode: str = "manual"
    global_proxy: bool = False
    domain_strategy: str = "AsIs"
    geoip_url: str = ""
    geosite_url: str = ""
    direct_sites: list[str] = field(default_factory=list)
    direct_ip: list[str] = field(default_factory=list)
    proxy_sites: list[str] = field(default_factory=list)
    proxy_ip: list[str] = field(default_factory=list)
    block_sites: list[str] = field(default_factory=list)
    block_ip: list[str] = field(default_factory=list)
    dns_hosts: dict[str, str] = field(default_factory=dict)
    route_order: list[str] = field(default_factory=lambda: ["block", "direct", "proxy"])
    source_subscription_id: str | None = None
    provider_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    domestic_dns_domain: str = ""
    domestic_dns_ip: str = ""
    domestic_dns_type: str = ""
    remote_dns_domain: str = ""
    remote_dns_ip: str = ""
    remote_dns_type: str = ""
    fake_dns: bool = False
    last_updated: str = ""
    supported_entry_count: int = 0
    stored_only_fields: list[str] = field(default_factory=list)
    ignored_fields: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)

    @property
    def has_geodata_urls(self) -> bool:
        return bool(self.geoip_url or self.geosite_url)

    @property
    def total_rules(self) -> int:
        return (
            len(self.direct_sites)
            + len(self.direct_ip)
            + len(self.proxy_sites)
            + len(self.proxy_ip)
            + len(self.block_sites)
            + len(self.block_ip)
        )
