"""ViewModel — преобразование сырого status dict в типизированные UI-строки."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def humanize_bytes(value: int | None) -> str:
    """Человеко-читаемый размер: 1024 -> '1.0 KB'."""
    if value is None or value < 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}"


def humanize_rate(value: float | None) -> str:
    """Человеко-читаемая скорость."""
    if value is None or value < 0:
        return "—"
    return f"{humanize_bytes(int(value))}/s"


@dataclass
class StatusViewModel:
    """Типизированное представление статуса для UI.

    Оборачивает сырой словарь collect_status() и предоставляет
    структурированный доступ к полям. Все русские строки — здесь.
    """

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # ── Сводка ──────────────────────────────────────────────────

    @property
    def connection_label(self) -> str:
        return self._raw.get("summary", {}).get("label", "—")

    @property
    def connection_status(self) -> str:
        return self._raw.get("summary", {}).get("status", "disconnected")

    @property
    def is_connected(self) -> bool:
        return self._raw.get("processes", {}).get("xray_alive", False)

    # ── Активный узел ───────────────────────────────────────────

    @property
    def active_node_name(self) -> str:
        node = self._raw.get("active_node")
        return node.get("name", "—") if node else "—"

    @property
    def active_node_protocol(self) -> str:
        node = self._raw.get("active_node")
        if node is None:
            return ""
        normalized = node.get("normalized", {})
        return normalized.get("protocol", "")

    @property
    def active_node_address(self) -> str:
        node = self._raw.get("active_node")
        if node is None:
            return ""
        normalized = node.get("normalized", {})
        host = normalized.get("address", "")
        port = normalized.get("port", "")
        return f"{host}:{port}" if host and port else ""

    # ── Трафик ──────────────────────────────────────────────────

    @property
    def traffic_rx_text(self) -> str:
        traffic = self._raw.get("traffic", {})
        return f"↓ {humanize_bytes(traffic.get('rx_total'))}"

    @property
    def traffic_tx_text(self) -> str:
        traffic = self._raw.get("traffic", {})
        return f"↑ {humanize_bytes(traffic.get('tx_total'))}"

    @property
    def traffic_rx_rate(self) -> str:
        traffic = self._raw.get("traffic", {})
        return humanize_rate(traffic.get("rx_rate"))

    @property
    def traffic_tx_rate(self) -> str:
        traffic = self._raw.get("traffic", {})
        return humanize_rate(traffic.get("tx_rate"))

    # ── Маршрутизация ───────────────────────────────────────────

    @property
    def routing_active_profile_name(self) -> str:
        routing = self._raw.get("routing", {})
        rp = routing.get("active_profile")
        return rp.get("name", "—") if rp else "—"

    @property
    def direct_report_entries(self) -> list[dict[str, Any]]:
        return self._raw.get("direct_report", {}).get("entries", [])

    # ── Процессы ────────────────────────────────────────────────

    @property
    def xray_pid(self) -> int | None:
        p = self._raw.get("processes", {}).get("xray_pid")
        return int(p) if p else None

    @property
    def xray_running_since(self) -> str:
        return self._raw.get("processes", {}).get("xray_started_at", "—")

    # ── Пинг и логи ─────────────────────────────────────────────

    @property
    def ping_cache(self) -> dict[str, Any]:
        return self._raw.get("ping", {}).get("cache", {})

    def ping_for_node(self, profile_id: str, node_id: str) -> str:
        key = f"{profile_id}:{node_id}"
        val = self.ping_cache.get(key, "—")
        return str(val) if val is not None else "—"

    # ── Сырой доступ (для обратной совместимости) ────────────────

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)


def build_view_model(status_dict: dict[str, Any]) -> StatusViewModel:
    """Фабрика: сырой status dict → ViewModel."""
    return StatusViewModel(_raw=status_dict)
