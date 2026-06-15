"""Фабрики: преобразование dict (store/parser) ↔ доменные сущности."""
from __future__ import annotations

from typing import Any

from .entities import Node, Profile, RoutingProfile, Subscription
from .value_objects import ProtocolConfig, TransportHint


# ── Node ────────────────────────────────────────────────────────────

def node_from_store_dict(d: dict[str, Any]) -> Node:
    """Восстановить Node из записи store (profile[\"nodes\"][i])."""
    normalized: dict[str, Any] = d.get("normalized", {})
    pc = _protocol_config_from_normalized(normalized)
    hint = _transport_hint_from_normalized(normalized)

    return Node(
        id=str(d.get("id", "")),
        profile_id="",  # заполняется при добавлении в профиль
        name=str(d.get("name", "")),
        protocol_config=pc,
        fingerprint=str(d.get("fingerprint", "")),
        raw_uri=str(d.get("raw_uri", "")),
        enabled=bool(d.get("enabled", True)),
        user_renamed=bool(d.get("user_renamed", False)),
        parse_error=str(d.get("parse_error", "")),
        transport_hint=hint,
        created_at=str(d.get("created_at", "")),
        updated_at=str(d.get("updated_at", "")),
    )


def node_to_store_dict(node: Node) -> dict[str, Any]:
    """Сериализовать Node в запись store."""
    return {
        "id": node.id,
        "fingerprint": node.fingerprint,
        "name": node.name,
        "protocol": node.protocol_config.protocol,
        "raw_uri": node.raw_uri,
        "origin": {"kind": "manual_import", "subscription_id": None},
        "enabled": node.enabled,
        "user_renamed": node.user_renamed,
        "parse_error": node.parse_error,
        "normalized": _protocol_config_to_normalized(node.protocol_config),
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


# ── Profile ─────────────────────────────────────────────────────────

def profile_from_store_dict(d: dict[str, Any]) -> Profile:
    """Восстановить Profile из записи store (store[\"profiles\"][i])."""
    nodes = []
    for nd in d.get("nodes", []):
        node = node_from_store_dict(nd)
        node.profile_id = d.get("id", "")
        nodes.append(node)

    return Profile(
        id=str(d.get("id", "")),
        name=str(d.get("name", "")),
        kind=str(d.get("kind", "manual")),
        enabled=bool(d.get("enabled", True)),
        source_subscription_id=_none_or_str(d.get("source_subscription_id")),
        nodes=nodes,
    )


def profile_to_store_dict(profile: Profile) -> dict[str, Any]:
    """Сериализовать Profile в запись store."""
    return {
        "id": profile.id,
        "kind": profile.kind,
        "name": profile.name,
        "enabled": profile.enabled,
        "source_subscription_id": profile.source_subscription_id,
        "nodes": [node_to_store_dict(n) for n in profile.nodes],
    }


# ── Subscription ────────────────────────────────────────────────────

def subscription_from_store_dict(d: dict[str, Any]) -> Subscription:
    """Восстановить Subscription из записи store."""
    return Subscription(
        id=str(d.get("id", "")),
        url=str(d.get("url", "")),
        name=str(d.get("name", "")),
        enabled=bool(d.get("enabled", True)),
        etag=str(d.get("etag", "")),
        last_modified=str(d.get("last_modified", "")),
        last_success_at=_none_or_str(d.get("last_success_at")),
        last_status=str(d.get("last_status", "never")),
        last_error=str(d.get("last_error", "")),
        profile_id=_none_or_str(d.get("profile_id")),
        provider_id=str(d.get("provider_id", "")),
        provider_id_source=str(d.get("provider_id_source", "")),
        routing_profile_id=_none_or_str(d.get("routing_profile_id")),
        last_routing_status=str(d.get("last_routing_status", "never")),
        last_routing_error=str(d.get("last_routing_error", "")),
    )


def subscription_to_store_dict(sub: Subscription) -> dict[str, Any]:
    """Сериализовать Subscription в запись store."""
    return {
        "id": sub.id,
        "name": sub.name,
        "url": sub.url,
        "enabled": sub.enabled,
        "etag": sub.etag,
        "last_modified": sub.last_modified,
        "last_success_at": sub.last_success_at,
        "last_status": sub.last_status,
        "last_error": sub.last_error,
        "profile_id": sub.profile_id,
        "provider_id": sub.provider_id,
        "provider_id_source": sub.provider_id_source,
        "routing_profile_id": sub.routing_profile_id,
        "last_routing_status": sub.last_routing_status,
        "last_routing_error": sub.last_routing_error,
    }


# ── RoutingProfile ──────────────────────────────────────────────────

def routing_profile_from_store_dict(d: dict[str, Any]) -> RoutingProfile:
    """Восстановить RoutingProfile из записи store."""
    return RoutingProfile(
        id=str(d.get("id", "")),
        name=str(d.get("name", "")),
        name_key=str(d.get("name_key", "")),
        enabled=bool(d.get("enabled", True)),
        auto_managed=bool(d.get("auto_managed", False)),
        source_kind=str(d.get("source_kind", "manual_import")),
        source_format=str(d.get("source_format", "json")),
        activation_mode=str(d.get("activation_mode", "manual")),
        global_proxy=bool(d.get("global_proxy", False)),
        domain_strategy=str(d.get("domain_strategy", "AsIs")),
        geoip_url=str(d.get("geoip_url", "")),
        geosite_url=str(d.get("geosite_url", "")),
        direct_sites=list(d.get("direct_sites", [])),
        direct_ip=list(d.get("direct_ip", [])),
        proxy_sites=list(d.get("proxy_sites", [])),
        proxy_ip=list(d.get("proxy_ip", [])),
        block_sites=list(d.get("block_sites", [])),
        block_ip=list(d.get("block_ip", [])),
        dns_hosts=dict(d.get("dns_hosts", {})),
        route_order=list(d.get("route_order", ["block", "direct", "proxy"])),
        source_subscription_id=_none_or_str(d.get("source_subscription_id")),
        provider_id=str(d.get("provider_id", "")),
        created_at=str(d.get("created_at", "")),
        updated_at=str(d.get("updated_at", "")),
        raw_payload=dict(d.get("raw_payload", {})) if isinstance(d.get("raw_payload"), dict) else {},
        domestic_dns_domain=str(d.get("domestic_dns_domain", "")),
        domestic_dns_ip=str(d.get("domestic_dns_ip", "")),
        domestic_dns_type=str(d.get("domestic_dns_type", "")),
        remote_dns_domain=str(d.get("remote_dns_domain", "")),
        remote_dns_ip=str(d.get("remote_dns_ip", "")),
        remote_dns_type=str(d.get("remote_dns_type", "")),
        fake_dns=bool(d.get("fake_dns", False)),
        last_updated=str(d.get("last_updated", "")),
        supported_entry_count=int(d.get("supported_entry_count", 0)),
        stored_only_fields=list(d.get("stored_only_fields", [])),
        ignored_fields=list(d.get("ignored_fields", [])),
        unknown_fields=list(d.get("unknown_fields", [])),
    )


# ── Вспомогательные ─────────────────────────────────────────────────

def _protocol_config_from_normalized(normalized: dict[str, Any]) -> ProtocolConfig:
    return ProtocolConfig(
        protocol=str(normalized.get("protocol", "")),
        address=str(normalized.get("address", "")),
        port=int(normalized.get("port", 0)),
        network=str(normalized.get("network", "tcp")),
        security=str(normalized.get("security", "none")),
        host=str(normalized.get("host", "")),
        path=str(normalized.get("path", "")),
        server_name=str(normalized.get("server_name", "")),
        service_name=str(normalized.get("service_name", "")),
        grpc_authority=str(normalized.get("grpc_authority", "")),
        fingerprint=str(normalized.get("fingerprint", "")),
        public_key=str(normalized.get("public_key", "")),
        short_id=str(normalized.get("short_id", "")),
        spider_x=str(normalized.get("spider_x", "/")),
        mode=str(normalized.get("mode", "auto")),
        xhttp_extra=dict(normalized.get("xhttp_extra", {})),
        alpn=list(normalized.get("alpn", [])),
        allow_insecure=bool(normalized.get("allow_insecure", False)),
        uuid=str(normalized.get("uuid", "")),
        encryption=str(normalized.get("encryption", "none")),
        flow=str(normalized.get("flow", "")),
        password=str(normalized.get("password", "")),
        alter_id=int(normalized.get("alter_id", 0)),
        cipher=str(normalized.get("cipher", "auto")),
        method=str(normalized.get("method", "")),
    )


def _protocol_config_to_normalized(pc: ProtocolConfig) -> dict[str, Any]:
    return {
        "protocol": pc.protocol,
        "address": pc.address,
        "port": pc.port,
        "network": pc.network,
        "security": pc.security,
        "host": pc.host,
        "path": pc.path,
        "server_name": pc.server_name,
        "service_name": pc.service_name,
        "grpc_authority": pc.grpc_authority,
        "fingerprint": pc.fingerprint,
        "public_key": pc.public_key,
        "short_id": pc.short_id,
        "spider_x": pc.spider_x,
        "mode": pc.mode,
        "xhttp_extra": pc.xhttp_extra,
        "alpn": pc.alpn,
        "allow_insecure": pc.allow_insecure,
        "uuid": pc.uuid,
        "encryption": pc.encryption,
        "flow": pc.flow,
        "password": pc.password,
        "alter_id": pc.alter_id,
        "cipher": pc.cipher,
        "method": pc.method,
    }


def _transport_hint_from_normalized(normalized: dict[str, Any]) -> TransportHint | None:
    interface = normalized.get("interface")
    mark = normalized.get("mark")
    if interface or mark is not None:
        return TransportHint(interface=str(interface) if interface else None, mark=int(mark) if mark is not None else None)
    return None


def _none_or_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
