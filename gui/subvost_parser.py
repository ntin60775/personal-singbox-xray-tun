from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


SUPPORTED_SCHEMES = {"vless", "vmess", "trojan", "ss"}
SUPPORTED_LINK_NETWORKS = {"tcp", "ws", "grpc", "xhttp"}
SUPPORTED_LINK_SECURITIES = {"none", "tls", "reality"}
SUPPORTED_VMESS_NETWORKS = {"tcp", "ws", "grpc"}
SUPPORTED_VMESS_SECURITIES = {"none", "tls"}
SUPPORTED_SS_METHODS = {
    "aes-128-gcm",
    "aes-256-gcm",
    "chacha20-ietf-poly1305",
    "2022-blake3-aes-128-gcm",
    "2022-blake3-aes-256-gcm",
    "2022-blake3-chacha20-poly1305",
}
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
PLACEHOLDER_TEXT_MARKERS = (
    "не поддерж",
    "поддерживаетя",
    "обратись к",
    "@provider_support",
    "not support",
)
HAPP_ROUTING_PREFIX = "happ://routing/"


class ParseError(ValueError):
    pass


def _decode_base64(value: str) -> bytes:
    cleaned = "".join(value.strip().split())
    padding = "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((cleaned + padding).encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ParseError("Не удалось декодировать base64-фрагмент.") from exc


def _decode_base64_text(value: str) -> str:
    try:
        return _decode_base64(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("Base64-фрагмент не является UTF-8 текстом.") from exc


def _single_value_query(raw_query: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, values in parse_qs(raw_query, keep_blank_values=True).items():
        result[key] = values[-1]
    return result


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _bool_value(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _default_name(name: str | None, protocol: str, address: str, port: int) -> str:
    trimmed = (name or "").strip()
    if trimmed:
        return trimmed
    return f"{protocol.upper()} {address}:{port}"


def _fingerprint_payload(normalized: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in normalized.items()
        if key not in {"display_name", "raw_uri", "origin_uri"}
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _placeholder_message(normalized: dict[str, Any]) -> str | None:
    address = str(normalized.get("address", "")).strip().lower()
    port = int(normalized.get("port", 0) or 0)
    uuid = str(normalized.get("uuid", "")).strip().lower()
    display_name = str(normalized.get("display_name", "")).strip()
    combined_text = " ".join(
        part.strip().lower()
        for part in [str(normalized.get("display_name", "")), str(normalized.get("raw_uri", ""))]
        if part
    )

    looks_like_stub_endpoint = address in {"0.0.0.0", "::", "[::]"} and port in {0, 1}
    has_stub_text = any(marker in combined_text for marker in PLACEHOLDER_TEXT_MARKERS)
    has_stub_identity = uuid == ZERO_UUID

    if looks_like_stub_endpoint and (has_stub_text or has_stub_identity):
        if display_name:
            suffix = "" if display_name.endswith((".", "!", "?")) else "."
            return f"Провайдер вернул заглушку: {display_name}{suffix}"
        return (
            "Провайдер вернул заглушку вместо рабочего узла. "
            "Вероятно, эту подписку нужно запрашивать через xray-совместимый клиент."
        )
    return None


def _finalize_parsed_proxy(normalized: dict[str, Any]) -> dict[str, Any]:
    message = _placeholder_message(normalized)
    if message:
        raise ParseError(message)
    return normalized


def _ensure_supported_query_keys(query: dict[str, str], allowed_keys: set[str]) -> None:
    unexpected = sorted(key for key, value in query.items() if value and key not in allowed_keys)
    if unexpected:
        raise ParseError(f"Неподдерживаемые параметры ссылки: {', '.join(unexpected)}.")


def _parse_stream_common(
    query: dict[str, str],
    *,
    protocol: str,
    allowed_networks: set[str],
    allowed_securities: set[str],
) -> dict[str, Any]:
    network = (query.get("type") or "tcp").strip().lower()
    if network not in allowed_networks:
        raise ParseError(f"Неподдерживаемый transport '{network}' для {protocol}.")

    security = (query.get("security") or "none").strip().lower()
    if security not in allowed_securities:
        raise ParseError(f"Неподдерживаемая security '{security}' для {protocol}.")

    host = query.get("host", "").strip()
    path = query.get("path", "").strip()
    server_name = (query.get("sni") or query.get("serverName") or "").strip()
    service_name = (query.get("serviceName") or query.get("service_name") or "").strip()
    grpc_authority = query.get("authority", "").strip()
    fingerprint = (query.get("fp") or query.get("fingerprint") or "").strip()
    public_key = (query.get("pbk") or query.get("publicKey") or "").strip()
    short_id = (query.get("sid") or query.get("shortId") or "").strip()
    spider_x = (query.get("spx") or query.get("spiderX") or "/").strip() or "/"
    mode = (query.get("mode") or "auto").strip()
    xhttp_extra: dict[str, Any] = {}
    alpn = _split_csv(query.get("alpn"))
    allow_insecure = _bool_value(query.get("allowInsecure") or query.get("insecure"))

    extra_value = (query.get("extra") or "").strip()
    if extra_value:
        try:
            parsed_extra = json.loads(extra_value)
        except json.JSONDecodeError as exc:
            raise ParseError("Параметр extra должен быть JSON-объектом.") from exc
        if not isinstance(parsed_extra, dict):
            raise ParseError("Параметр extra должен быть JSON-объектом.")
        xhttp_extra = parsed_extra

    if network in {"ws", "xhttp"} and not path:
        path = "/"

    if network == "grpc" and not service_name and path:
        service_name = path.lstrip("/")

    if network == "grpc" and not service_name:
        raise ParseError("Для gRPC-ссылки обязателен serviceName.")

    if security == "tls" and not server_name:
        raise ParseError("Для TLS-ссылки обязателен sni/serverName.")

    if security == "reality":
        if not server_name:
            raise ParseError("Для REALITY-ссылки обязателен sni/serverName.")
        if not public_key:
            raise ParseError("Для REALITY-ссылки обязателен publicKey/pbk.")
        if not short_id:
            raise ParseError("Для REALITY-ссылки обязателен shortId/sid.")
        if not fingerprint:
            raise ParseError("Для REALITY-ссылки обязателен fingerprint/fp.")

    return {
        "network": network,
        "security": security,
        "host": host,
        "path": path,
        "server_name": server_name,
        "service_name": service_name,
        "grpc_authority": grpc_authority,
        "fingerprint": fingerprint,
        "public_key": public_key,
        "short_id": short_id,
        "spider_x": spider_x,
        "mode": mode,
        "xhttp_extra": xhttp_extra,
        "alpn": alpn,
        "allow_insecure": allow_insecure,
    }


def parse_vless_uri(raw_uri: str) -> dict[str, Any]:
    parsed = urlsplit(raw_uri)
    if not parsed.username or not parsed.hostname or parsed.port is None:
        raise ParseError("VLESS-ссылка должна содержать UUID, адрес и порт.")

    query = _single_value_query(parsed.query)
    _ensure_supported_query_keys(
        query,
        {
            "type",
            "security",
            "sni",
            "serverName",
            "host",
            "path",
            "serviceName",
            "service_name",
            "authority",
            "fp",
            "fingerprint",
            "pbk",
            "publicKey",
            "sid",
            "shortId",
            "spx",
            "spiderX",
            "mode",
            "extra",
            "alpn",
            "allowInsecure",
            "insecure",
            "flow",
            "encryption",
        },
    )

    encryption = (query.get("encryption") or "none").strip().lower()
    if encryption != "none":
        raise ParseError("Для VLESS поддерживается только encryption=none.")

    normalized = {
        "protocol": "vless",
        "address": parsed.hostname,
        "port": parsed.port,
        "uuid": parsed.username,
        "encryption": "none",
        "flow": query.get("flow", "").strip(),
        "display_name": _default_name(unquote(parsed.fragment), "vless", parsed.hostname, parsed.port),
        "raw_uri": raw_uri.strip(),
        **_parse_stream_common(
            query,
            protocol="vless",
            allowed_networks=SUPPORTED_LINK_NETWORKS,
            allowed_securities=SUPPORTED_LINK_SECURITIES,
        ),
    }
    normalized["fingerprint_hash"] = _fingerprint_payload(normalized)
    return normalized


def parse_trojan_uri(raw_uri: str) -> dict[str, Any]:
    parsed = urlsplit(raw_uri)
    if not parsed.username or not parsed.hostname or parsed.port is None:
        raise ParseError("Trojan-ссылка должна содержать пароль, адрес и порт.")

    query = _single_value_query(parsed.query)
    _ensure_supported_query_keys(
        query,
        {
            "type",
            "security",
            "sni",
            "serverName",
            "host",
            "path",
            "serviceName",
            "service_name",
            "authority",
            "fp",
            "fingerprint",
            "pbk",
            "publicKey",
            "sid",
            "shortId",
            "spx",
            "spiderX",
            "mode",
            "extra",
            "alpn",
            "allowInsecure",
            "insecure",
        },
    )

    normalized = {
        "protocol": "trojan",
        "address": parsed.hostname,
        "port": parsed.port,
        "password": parsed.username,
        "display_name": _default_name(unquote(parsed.fragment), "trojan", parsed.hostname, parsed.port),
        "raw_uri": raw_uri.strip(),
        **_parse_stream_common(
            query,
            protocol="trojan",
            allowed_networks=SUPPORTED_LINK_NETWORKS,
            allowed_securities=SUPPORTED_LINK_SECURITIES,
        ),
    }
    normalized["fingerprint_hash"] = _fingerprint_payload(normalized)
    return normalized


def parse_vmess_uri(raw_uri: str) -> dict[str, Any]:
    body = raw_uri[len("vmess://") :].strip()
    payload = json.loads(_decode_base64_text(body))
    address = str(payload.get("add", "")).strip()
    port_raw = str(payload.get("port", "")).strip()
    user_id = str(payload.get("id", "")).strip()
    if not address or not port_raw.isdigit() or not user_id:
        raise ParseError("Vmess-ссылка должна содержать add, port и id.")

    network = str(payload.get("net", "tcp")).strip().lower()
    if network not in SUPPORTED_VMESS_NETWORKS:
        raise ParseError(f"Неподдерживаемый transport '{network}' для vmess.")

    stream_type = str(payload.get("type", "")).strip().lower()
    if stream_type not in {"", "none"}:
        raise ParseError(f"Неподдерживаемый header/type '{stream_type}' для vmess.")

    security = str(payload.get("tls") or payload.get("security") or "none").strip().lower()
    if security == "":
        security = "none"
    if security not in SUPPORTED_VMESS_SECURITIES:
        raise ParseError(f"Неподдерживаемая security '{security}' для vmess.")

    service_name = ""
    path = str(payload.get("path", "")).strip()
    if network == "grpc":
        service_name = path.lstrip("/")
        if not service_name:
            service_name = str(payload.get("serviceName", "")).strip()
        if not service_name:
            raise ParseError("Для vmess gRPC обязателен path/serviceName.")
        path = ""
    elif network == "ws" and not path:
        path = "/"

    server_name = str(payload.get("sni", "")).strip()
    if security == "tls" and not server_name:
        raise ParseError("Для TLS-vmess обязателен sni.")

    try:
        alter_id = int(str(payload.get("aid", "0")).strip() or "0")
    except ValueError as exc:
        raise ParseError("aid в vmess должен быть целым числом.") from exc

    cipher = str(payload.get("scy", "auto")).strip() or "auto"

    normalized = {
        "protocol": "vmess",
        "address": address,
        "port": int(port_raw),
        "uuid": user_id,
        "alter_id": alter_id,
        "cipher": cipher,
        "network": network,
        "security": security,
        "host": str(payload.get("host", "")).strip(),
        "path": path,
        "server_name": server_name,
        "service_name": service_name,
        "grpc_authority": str(payload.get("authority", "")).strip(),
        "fingerprint": str(payload.get("fp", "")).strip(),
        "public_key": "",
        "short_id": "",
        "spider_x": "/",
        "mode": "auto",
        "xhttp_extra": {},
        "alpn": _split_csv(str(payload.get("alpn", "")).strip()),
        "allow_insecure": _bool_value(str(payload.get("allowInsecure", "")).strip()),
        "display_name": _default_name(str(payload.get("ps", "")).strip(), "vmess", address, int(port_raw)),
        "raw_uri": raw_uri.strip(),
    }
    normalized["fingerprint_hash"] = _fingerprint_payload(normalized)
    return normalized


def parse_ss_uri(raw_uri: str) -> dict[str, Any]:
    parsed = urlsplit(raw_uri)
    query = _single_value_query(parsed.query)
    plugin = query.get("plugin", "").strip()
    if plugin:
        raise ParseError("SIP002 plugin для shadowsocks не поддерживается.")

    body = raw_uri[len("ss://") :]
    body = body.split("#", 1)[0].split("?", 1)[0]
    credential_part = ""
    host_port_part = ""
    decode_direct_userinfo = False
    if "@" in body:
        credential_part, host_port_part = body.rsplit("@", 1)
        if ":" not in credential_part:
            credential_part = _decode_base64_text(credential_part)
        else:
            decode_direct_userinfo = True
    else:
        decoded = _decode_base64_text(body)
        if "@" not in decoded:
            raise ParseError("Shadowsocks-ссылка не содержит host:port.")
        credential_part, host_port_part = decoded.rsplit("@", 1)

    if ":" not in credential_part:
        raise ParseError("Shadowsocks-ссылка не содержит method:password.")

    method, password = credential_part.split(":", 1)
    if decode_direct_userinfo:
        method = unquote(method)
        password = unquote(password)
    method = method.strip().lower()
    password = password.strip()
    if not method or not password:
        raise ParseError("Shadowsocks-ссылка должна содержать method и password.")
    if method not in SUPPORTED_SS_METHODS:
        raise ParseError(f"Неподдерживаемый shadowsocks method '{method}'.")

    authority = urlsplit(f"ss://dummy@{host_port_part}")
    if not authority.hostname or authority.port is None:
        raise ParseError("Shadowsocks-ссылка должна содержать адрес и порт.")

    normalized = {
        "protocol": "ss",
        "address": authority.hostname,
        "port": authority.port,
        "method": method,
        "password": password,
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
        "xhttp_extra": {},
        "alpn": [],
        "allow_insecure": False,
        "display_name": _default_name(unquote(parsed.fragment), "ss", authority.hostname, authority.port),
        "raw_uri": raw_uri.strip(),
    }
    normalized["fingerprint_hash"] = _fingerprint_payload(normalized)
    return normalized


def parse_proxy_uri(raw_uri: str) -> dict[str, Any]:
    value = raw_uri.strip()
    if not value:
        raise ParseError("Пустая строка не является ссылкой конфигурации.")

    scheme = urlsplit(value).scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise ParseError(f"Неподдерживаемая схема '{scheme}'.")

    if scheme == "vless":
        return _finalize_parsed_proxy(parse_vless_uri(value))
    if scheme == "vmess":
        return _finalize_parsed_proxy(parse_vmess_uri(value))
    if scheme == "trojan":
        return _finalize_parsed_proxy(parse_trojan_uri(value))
    return _finalize_parsed_proxy(parse_ss_uri(value))


def preview_links(raw_text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            normalized = parse_proxy_uri(line)
            results.append(
                {
                    "line_number": index,
                    "raw_uri": line,
                    "valid": True,
                    "error": "",
                    "fingerprint": normalized["fingerprint_hash"],
                    "normalized": normalized,
                }
            )
        except ParseError as exc:
            results.append(
                {
                    "line_number": index,
                    "raw_uri": line,
                    "valid": False,
                    "error": str(exc),
                    "fingerprint": "",
                    "normalized": {},
                }
            )
    return results


def parse_subscription_payload(payload: bytes) -> tuple[list[str], str]:
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        raise ParseError("Подписка вернула пустой ответ.")

    plain_lines = [line.strip() for line in text.splitlines() if line.strip()]
    plain_proxy_lines = [line for line in plain_lines if urlsplit(line).scheme.lower() in SUPPORTED_SCHEMES]
    plain_ignorable_lines = [line for line in plain_lines if line.startswith(HAPP_ROUTING_PREFIX)]
    if plain_proxy_lines and len(plain_proxy_lines) + len(plain_ignorable_lines) == len(plain_lines):
        return plain_proxy_lines, "plain_text"

    decoded_text = _decode_base64_text(text).strip()
    decoded_lines = [line.strip() for line in decoded_text.splitlines() if line.strip()]
    decoded_proxy_lines = [line for line in decoded_lines if urlsplit(line).scheme.lower() in SUPPORTED_SCHEMES]
    decoded_ignorable_lines = [line for line in decoded_lines if line.startswith(HAPP_ROUTING_PREFIX)]
    if decoded_proxy_lines and len(decoded_proxy_lines) + len(decoded_ignorable_lines) == len(decoded_lines):
        return decoded_proxy_lines, "base64"

    raise ParseError("Формат подписки не распознан: ожидался plain-text или base64-список ссылок.")


def load_links_from_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")
