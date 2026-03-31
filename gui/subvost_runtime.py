from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


PLACEHOLDER_MARKERS = {
    "REPLACE_WITH_REALITY_UUID",
    "REPLACE_WITH_REALITY_PUBLIC_KEY",
    "REPLACE_WITH_REALITY_SHORT_ID",
}


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


def config_has_placeholders(config: dict[str, Any]) -> bool:
    payload = json.dumps(config, ensure_ascii=False)
    return any(marker in payload for marker in PLACEHOLDER_MARKERS)


def node_can_render_runtime(node: dict[str, Any] | None) -> bool:
    if not node:
        return False
    normalized = node.get("normalized") or {}
    if not normalized:
        return False
    if node.get("parse_error"):
        return False
    return bool(node.get("enabled", True))


def extract_node_from_existing_config(config: dict[str, Any]) -> dict[str, Any] | None:
    proxy = find_proxy_outbound(config)
    if not proxy:
        return None

    protocol = str(proxy.get("protocol", "")).strip().lower()
    stream = proxy.get("streamSettings", {}) or {}
    network = str(stream.get("network") or "tcp").strip().lower()
    security = str(stream.get("security") or "none").strip().lower()

    if protocol == "shadowsocks":
        servers = proxy.get("settings", {}).get("servers", [])
        if not servers:
            return None
        server = servers[0]
        normalized = {
            "protocol": "ss",
            "address": server.get("address", ""),
            "port": int(server.get("port", 0) or 0),
            "method": server.get("method", ""),
            "password": server.get("password", ""),
            "network": "tcp",
            "security": "none",
            "host": "",
            "path": "",
            "server_name": "",
            "service_name": "",
            "grpc_authority": "",
            "fingerprint": "",
            "public_key": "",
            "short_id": "",
            "spider_x": "/",
            "mode": "auto",
            "alpn": [],
            "allow_insecure": False,
            "display_name": "Migrated from current config",
            "raw_uri": "",
        }
    elif protocol in {"vless", "vmess"}:
        vnext = proxy.get("settings", {}).get("vnext", [])
        if not vnext:
            return None
        endpoint = vnext[0]
        users = endpoint.get("users", [])
        if not users:
            return None
        user = users[0]
        normalized = {
            "protocol": protocol,
            "address": endpoint.get("address", ""),
            "port": int(endpoint.get("port", 0) or 0),
            "uuid": user.get("id", ""),
            "network": network,
            "security": security,
            "host": "",
            "path": "",
            "server_name": "",
            "service_name": "",
            "grpc_authority": "",
            "fingerprint": "",
            "public_key": "",
            "short_id": "",
            "spider_x": "/",
            "mode": "auto",
            "alpn": [],
            "allow_insecure": False,
            "display_name": "Migrated from current config",
            "raw_uri": "",
        }
        if protocol == "vless":
            normalized["encryption"] = user.get("encryption", "none")
            normalized["flow"] = user.get("flow", "")
        else:
            normalized["alter_id"] = int(user.get("alterId", 0) or 0)
            normalized["cipher"] = user.get("security", "auto")
    elif protocol == "trojan":
        servers = proxy.get("settings", {}).get("servers", [])
        if not servers:
            return None
        server = servers[0]
        normalized = {
            "protocol": "trojan",
            "address": server.get("address", ""),
            "port": int(server.get("port", 0) or 0),
            "password": server.get("password", ""),
            "network": network,
            "security": security,
            "host": "",
            "path": "",
            "server_name": "",
            "service_name": "",
            "grpc_authority": "",
            "fingerprint": "",
            "public_key": "",
            "short_id": "",
            "spider_x": "/",
            "mode": "auto",
            "alpn": [],
            "allow_insecure": False,
            "display_name": "Migrated from current config",
            "raw_uri": "",
        }
    else:
        return None

    if normalized["port"] <= 0 or not normalized["address"]:
        return None

    if security == "tls":
        tls = stream.get("tlsSettings", {}) or {}
        normalized["server_name"] = tls.get("serverName", "")
        normalized["alpn"] = tls.get("alpn", []) or []
        normalized["allow_insecure"] = bool(tls.get("allowInsecure", False))
        normalized["fingerprint"] = tls.get("fingerprint", "")
    elif security == "reality":
        reality = stream.get("realitySettings", {}) or {}
        normalized["server_name"] = reality.get("serverName", "")
        normalized["fingerprint"] = reality.get("fingerprint", "")
        normalized["public_key"] = reality.get("publicKey", "")
        normalized["short_id"] = reality.get("shortId", "")
        normalized["spider_x"] = reality.get("spiderX", "/")

    if network == "ws":
        ws_settings = stream.get("wsSettings", {}) or {}
        normalized["path"] = ws_settings.get("path", "/")
        headers = ws_settings.get("headers", {}) or {}
        normalized["host"] = headers.get("Host", "")
    elif network == "grpc":
        grpc_settings = stream.get("grpcSettings", {}) or {}
        normalized["service_name"] = grpc_settings.get("serviceName", "")
        normalized["grpc_authority"] = grpc_settings.get("authority", "")
    elif network == "xhttp":
        xhttp_settings = stream.get("xhttpSettings", {}) or {}
        normalized["path"] = xhttp_settings.get("path", "/")
        normalized["host"] = xhttp_settings.get("host", "")
        normalized["mode"] = xhttp_settings.get("mode", "auto")

    return normalized


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
        template_xhttp = template_stream.get("xhttpSettings", {}) or {}
        if template_xhttp.get("extra"):
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


def render_runtime_config(template_config: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
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
    return config
