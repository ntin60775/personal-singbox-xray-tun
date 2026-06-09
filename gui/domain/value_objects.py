"""Value objects — неизменяемые типы без идентичности."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeAddress:
    """Адрес узла: хост, порт, транспорт."""
    host: str
    port: int
    transport: str = "tcp"  # "tcp", "ws", "grpc", "xhttp"

    def __str__(self) -> str:
        return f"{self.host}:{self.port}/{self.transport}"


@dataclass(frozen=True)
class ProtocolConfig:
    """Конфигурация протокола: общие для всех протоколов поля + специфичные."""
    protocol: str  # "vless", "vmess", "trojan", "ss"
    address: str
    port: int
    # Общие stream-поля
    network: str = "tcp"
    security: str = "none"
    host: str = ""
    path: str = ""
    server_name: str = ""
    service_name: str = ""
    grpc_authority: str = ""
    fingerprint: str = ""
    public_key: str = ""
    short_id: str = ""
    spider_x: str = "/"
    mode: str = "auto"
    xhttp_extra: dict[str, Any] = field(default_factory=dict)
    alpn: list[str] = field(default_factory=list)
    allow_insecure: bool = False
    # Протокол-специфичные
    uuid: str = ""  # VLESS, VMess
    encryption: str = "none"  # VLESS
    flow: str = ""  # VLESS
    password: str = ""  # Trojan, SS
    alter_id: int = 0  # VMess
    cipher: str = "auto"  # VMess
    method: str = ""  # SS

    @property
    def is_tls(self) -> bool:
        return self.security in ("tls", "reality")

    @property
    def is_reality(self) -> bool:
        return self.security == "reality"


@dataclass(frozen=True)
class TransportHint:
    """Подсказка для TUN-маршрутизации: interface + fwmark."""
    interface: str | None = None
    mark: int | None = None
