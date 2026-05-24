"""Alpaca broker event stream adapter boundary."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from qts.core import DataError
from qts.domain import BrokerEvent, BrokerEventType, Fill, Order

from .mapping import alpaca_order_to_domain, alpaca_order_to_fill_delta


class AlpacaBrokerEventClient(Protocol):
    """Small Alpaca trade-update stream surface consumed by the adapter."""

    def connect(self, *, channels: Sequence[str]) -> None:
        """Connect and subscribe to Alpaca trading event channels."""

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        """Yield Alpaca-shaped broker event payloads."""

    def close(self) -> None:
        """Release stream resources."""


@dataclass
class InMemoryAlpacaBrokerEventClient:
    """Deterministic Alpaca-like broker event client for tests."""

    messages: Sequence[Mapping[str, Any] | Sequence[Mapping[str, Any]]]
    connected: bool = False
    closed: bool = False
    subscriptions: list[dict[str, object]] = field(default_factory=list)

    def connect(self, *, channels: Sequence[str]) -> None:
        self.connected = True
        self.closed = False
        self.subscriptions.append({"channels": list(channels)})

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        if not self.connected:
            raise DataError("Alpaca broker event client is not connected")
        yield from self.messages

    def close(self) -> None:
        self.closed = True
        self.connected = False


class AlpacaBrokerEventSource:
    """Convert Alpaca trade-update payloads into normalized broker events."""

    def __init__(
        self,
        client: AlpacaBrokerEventClient,
        *,
        source: str = "alpaca_trade_updates",
        channels: Sequence[str] = ("trade_updates",),
    ) -> None:
        self.client = client
        self.source = source
        self.channels = list(channels)
        self.closed = False
        self._filled_quantities_by_order_id: dict[str, float] = {}

    def iter_events(self) -> Iterator[BrokerEvent]:
        self.client.connect(channels=self.channels)
        for message in self.client.iter_messages():
            for payload in _iter_payloads(message):
                yield from alpaca_trade_update_to_broker_events(
                    payload,
                    filled_quantities_by_order_id=self._filled_quantities_by_order_id,
                    source=self.source,
                )

    def close(self) -> None:
        self.client.close()
        self.closed = True


def alpaca_trade_update_to_broker_events(
    payload: Mapping[str, Any],
    *,
    filled_quantities_by_order_id: dict[str, float] | None = None,
    source: str = "alpaca_trade_updates",
) -> list[BrokerEvent]:
    """Normalize one Alpaca trade update into order/fill broker events."""
    update = _trade_update_payload(payload)
    event_type = str(update.get("event") or update.get("T") or update.get("type") or "").lower()
    if event_type in {"success", "subscription"}:
        return []
    if event_type in {"error", "err"}:
        message = update.get("msg") or update.get("message") or update
        raise DataError(f"Alpaca broker event error payload: {message}")

    raw_order = update.get("order")
    if not isinstance(raw_order, Mapping):
        if _looks_like_order_payload(update):
            raw_order = update
        else:
            raise DataError("Alpaca broker event payload requires an order mapping")
    order_payload = dict(raw_order)
    timestamp = update.get("timestamp") or update.get("t")
    if timestamp and not any(order_payload.get(key) for key in ("updated_at", "filled_at")):
        order_payload["updated_at"] = timestamp

    order = alpaca_order_to_domain(order_payload)
    state = filled_quantities_by_order_id if filled_quantities_by_order_id is not None else {}
    previous_quantity = state.get(order.order_id, 0.0)
    fill = alpaca_order_to_fill_delta(
        order_payload,
        previous_quantity,
        source=source,
    )
    state[order.order_id] = max(previous_quantity, order.filled_quantity)

    events = [_broker_event_from_order(order, source=source)]
    if fill is not None:
        events.append(_broker_event_from_fill(fill, source=source))
    return events


def _trade_update_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    if isinstance(data, Mapping):
        return data
    return payload


def _iter_payloads(
    message: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> Iterator[Mapping[str, Any]]:
    if isinstance(message, Mapping):
        yield message
        return
    if isinstance(message, Sequence) and not isinstance(message, (str, bytes, bytearray)):
        for payload in message:
            if not isinstance(payload, Mapping):
                raise DataError("Alpaca broker event message list must contain mappings")
            yield payload
        return
    raise DataError(f"unsupported Alpaca broker event message type: {type(message).__name__}")


def _looks_like_order_payload(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("id") and payload.get("symbol") and payload.get("status"))


def _broker_event_from_order(order: Order, *, source: str) -> BrokerEvent:
    timestamp = order.updated_at or order.created_at
    event_id = (
        f"order:{order.order_id}:{order.status.value}:"
        f"{_quantity_key(order.filled_quantity)}:{_quantity_key(order.remaining_quantity)}:"
        f"{timestamp.isoformat().replace('+00:00', 'Z')}"
    )
    return BrokerEvent(
        event_id=event_id,
        event_type=BrokerEventType.ORDER_UPDATE,
        timestamp=timestamp,
        source=source,
        order=order,
    )


def _broker_event_from_fill(fill: Fill, *, source: str) -> BrokerEvent:
    return BrokerEvent(
        event_id=f"fill:{fill.fill_id}",
        event_type=BrokerEventType.FILL,
        timestamp=fill.timestamp,
        source=source,
        fill=fill,
    )


def _quantity_key(value: float | int | None) -> str:
    if value is None:
        return "none"
    return f"{float(value):.12g}"


__all__ = [
    "AlpacaBrokerEventClient",
    "AlpacaBrokerEventSource",
    "InMemoryAlpacaBrokerEventClient",
    "alpaca_trade_update_to_broker_events",
]
