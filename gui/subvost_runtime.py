from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .subvost_routing import apply_routing_profile_to_config


def read_json_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def find_proxy_outbound(config: dict[str, Any]) -> dict[str, Any] | None:
    for outbound in config.get("outbounds", []):
        if outbound.get("tag") == "proxy":
            return outbound
    return None


def find_tagged_entry(config: dict[str, Any], collection_name: str, tag: str) -> dict[str, Any] | None:
    for item in config.get(collection_name, []):
        if item.get("tag") == tag:
            return item
    return None


def node_can_render_runtime(node: dict[str, Any] | None) -> bool:
    if not node:
        return False
    normalized = node.get("normalized") or {}
    if not normalized:
        return False
    if node.get("parse_error"):
        return False
    return bool(node.get("enabled", True))


def _build_stream_settings(normalized: dict[str, Any], template_stream: dict[str, Any]) -> dict[str, Any]:
    stream_settings: dict[str, Any] = {
        "network": normalized.get("network", "tcp"),
        "security": normalized.get("security", "none"),
    }
    if template_stream.get("sockopt"):
        stream_settings["sockopt"] = copy.deepcopy(template_stream["sockopt"])

    network = normalized.get("network")
    if network == "ws":
        ws_settings: dict[str, Any] = {"path": normalized.get("path") or "/"}
        host = normalized.get("host", "")
        if host:
            ws_settings["headers"] = {"Host": host}
        stream_settings["wsSettings"] = ws_settings
    elif network == "grpc":
        grpc_settings: dict[str, Any] = {"serviceName": normalized.get("service_name", "")}
        authority = normalized.get("grpc_authority", "")
        if authority:
            grpc_settings["authority"] = authority
        stream_settings["grpcSettings"] = grpc_settings
    elif network == "xhttp":
        xhttp_settings: dict[str, Any] = {
            "host": normalized.get("host", ""),
            "path": normalized.get("path") or "/",
            "mode": normalized.get("mode", "auto") or "auto",
        }
        xhttp_extra = normalized.get("xhttp_extra") or {}
        template_xhttp = template_stream.get("xhttpSettings", {}) or {}
        if xhttp_extra:
            xhttp_settings["extra"] = copy.deepcopy(xhttp_extra)
        elif template_xhttp.get("extra"):
            xhttp_settings["extra"] = copy.deepcopy(template_xhttp["extra"])
        stream_settings["xhttpSettings"] = xhttp_settings

    security = normalized.get("security", "none")
    if security == "tls":
        tls_settings: dict[str, Any] = {
            "serverName": normalized.get("server_name", ""),
        }
        if normalized.get("alpn"):
            tls_settings["alpn"] = normalized["alpn"]
        if normalized.get("allow_insecure"):
            tls_settings["allowInsecure"] = True
        if normalized.get("fingerprint"):
            tls_settings["fingerprint"] = normalized["fingerprint"]
        stream_settings["tlsSettings"] = tls_settings
    elif security == "reality":
        stream_settings["realitySettings"] = {
            "serverName": normalized.get("server_name", ""),
            "fingerprint": normalized.get("fingerprint", ""),
            "publicKey": normalized.get("public_key", ""),
            "shortId": normalized.get("short_id", ""),
            "spiderX": normalized.get("spider_x", "/"),
        }

    return stream_settings


def build_proxy_outbound(normalized: dict[str, Any], template_outbound: dict[str, Any]) -> dict[str, Any]:
    protocol = normalized.get("protocol")
    template_stream = template_outbound.get("streamSettings", {}) or {}
    outbound: dict[str, Any] = {
        "tag": template_outbound.get("tag", "proxy"),
        "protocol": "shadowsocks" if protocol == "ss" else protocol,
    }

    if protocol == "vless":
        user = {
            "id": normalized.get("uuid", ""),
            "encryption": normalized.get("encryption", "none"),
        }
        if normalized.get("flow"):
            user["flow"] = normalized["flow"]
        outbound["settings"] = {
            "vnext": [
                {
                    "address": normalized.get("address", ""),
                    "port": normalized.get("port", 0),
                    "users": [user],
                }
            ]
        }
    elif protocol == "vmess":
        outbound["settings"] = {
            "vnext": [
                {
                    "address": normalized.get("address", ""),
                    "port": normalized.get("port", 0),
                    "users": [
                        {
                            "id": normalized.get("uuid", ""),
                            "alterId": normalized.get("alter_id", 0),
                            "security": normalized.get("cipher", "auto"),
                        }
                    ],
                }
            ]
        }
    elif protocol == "trojan":
        outbound["settings"] = {
            "servers": [
                {
                    "address": normalized.get("address", ""),
                    "port": normalized.get("port", 0),
                    "password": normalized.get("password", ""),
                }
            ]
        }
    elif protocol == "ss":
        outbound["settings"] = {
            "servers": [
                {
                    "address": normalized.get("address", ""),
                    "port": normalized.get("port", 0),
                    "method": normalized.get("method", ""),
                    "password": normalized.get("password", ""),
                }
            ]
        }
    else:
        raise ValueError(f"Неподдерживаемый protocol для runtime generation: {protocol}")

    outbound["streamSettings"] = _build_stream_settings(normalized, template_stream)
    return outbound


def render_runtime_config(
    template_config: dict[str, Any],
    node: dict[str, Any],
    routing_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not node_can_render_runtime(node):
        raise ValueError("Активный узел не может быть материализован в runtime-конфиг.")

    normalized = node.get("normalized") or {}
    config = copy.deepcopy(template_config)
    outbounds = config.get("outbounds", [])
    replaced = False
    for index, outbound in enumerate(outbounds):
        if outbound.get("tag") == "proxy":
            outbounds[index] = build_proxy_outbound(normalized, outbound)
            replaced = True
            break
    if not replaced:
        raise ValueError("В шаблоне xray не найден outbound с tag=proxy.")
    if routing_profile:
        config = apply_routing_profile_to_config(config, routing_profile)
    return config





