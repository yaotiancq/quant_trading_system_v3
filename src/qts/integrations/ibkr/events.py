"""IBKR broker event stream adapter boundary."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from qts.core import DataError
from qts.domain import BrokerEvent, BrokerEventType, Fill, Order, OrderRequest

from .mapping import ibkr_order_to_domain, ibkr_order_to_fill_delta


class IBKRBrokerEventClient(Protocol):
    """Small IBKR order-update stream surface consumed by the adapter."""

    def connect(self, *, account_id: str | None = None) -> None:
        """Connect and subscribe to IBKR broker lifecycle events."""

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        """Yield IBKR-shaped broker event payloads."""

    def close(self) -> None:
        """Release stream resources."""


@dataclass
class InMemoryIBKRBrokerEventClient:
    """Deterministic IBKR-like broker event client for tests."""

    messages: Sequence[Mapping[str, Any] | Sequence[Mapping[str, Any]]]
    connected: bool = False
    closed: bool = False
    subscriptions: list[dict[str, object]] = field(default_factory=list)

    def connect(self, *, account_id: str | None = None) -> None:
        self.connected = True
        self.closed = False
        self.subscriptions.append({"account_id": account_id})

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        if not self.connected:
            raise DataError("IBKR broker event client is not connected")
        yield from self.messages

    def close(self) -> None:
        self.closed = True
        self.connected = False


class IBKRBrokerEventSource:
    """Convert IBKR order-update payloads into normalized broker events."""

    def __init__(
        self,
        client: IBKRBrokerEventClient,
        *,
        account_id: str | None = None,
        source: str = "ibkr_order_updates",
        order_requests_by_order_id: Mapping[str, OrderRequest] | None = None,
    ) -> None:
        self.client = client
        self.account_id = account_id
        self.source = source
        self.order_requests_by_order_id = dict(order_requests_by_order_id or {})
        self.closed = False
        self._filled_quantities_by_order_id: dict[str, float] = {}

    def iter_events(self) -> Iterator[BrokerEvent]:
        self.client.connect(account_id=self.account_id)
        for message in self.client.iter_messages():
            for payload in _iter_payloads(message):
                yield from ibkr_order_update_to_broker_events(
                    payload,
                    account_id=self.account_id,
                    filled_quantities_by_order_id=self._filled_quantities_by_order_id,
                    order_requests_by_order_id=self.order_requests_by_order_id,
                    source=self.source,
                )

    def close(self) -> None:
        self.client.close()
        self.closed = True


def ibkr_order_update_to_broker_events(
    payload: Mapping[str, Any],
    *,
    account_id: str | None = None,
    filled_quantities_by_order_id: dict[str, float] | None = None,
    order_requests_by_order_id: Mapping[str, OrderRequest] | None = None,
    source: str = "ibkr_order_updates",
) -> list[BrokerEvent]:
    """Normalize one IBKR order update into order/fill broker events."""
    update = _order_update_payload(payload)
    event_type = str(update.get("event") or update.get("type") or update.get("topic") or "").lower()
    if event_type in {"success", "subscription", "subscribed"}:
        return []
    if event_type in {"error", "err"}:
        message = update.get("msg") or update.get("message") or update
        raise DataError(f"IBKR broker event error payload: {message}")
    if not _looks_like_order_payload(update):
        raise DataError("IBKR broker event payload requires order fields")

    order_requests = dict(order_requests_by_order_id or {})
    order_id = _order_id(update)
    order_request = order_requests.get(order_id)
    order = ibkr_order_to_domain(update, order_request=order_request, account_id=account_id)
    state = filled_quantities_by_order_id if filled_quantities_by_order_id is not None else {}
    previous_quantity = state.get(order.order_id, 0.0)
    fill = ibkr_order_to_fill_delta(
        update,
        previous_quantity,
        order_request=order_request,
        source=source,
    )
    state[order.order_id] = max(previous_quantity, order.filled_quantity)

    events = [_broker_event_from_order(order, source=source)]
    if fill is not None:
        events.append(_broker_event_from_fill(fill, source=source))
    return events


def _order_update_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    if isinstance(data, Mapping):
        return data
    order = payload.get("order")
    if isinstance(order, Mapping):
        return order
    return payload


def _iter_payloads(
    message: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> Iterator[Mapping[str, Any]]:
    if isinstance(message, Mapping):
        items = message.get("orders")
        if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)):
            for item in items:
                if not isinstance(item, Mapping):
                    raise DataError("IBKR broker event orders list must contain mappings")
                yield item
            return
        yield message
        return
    if isinstance(message, Sequence) and not isinstance(message, (str, bytes, bytearray)):
        for payload in message:
            if not isinstance(payload, Mapping):
                raise DataError("IBKR broker event message list must contain mappings")
            yield payload
        return
    raise DataError(f"unsupported IBKR broker event message type: {type(message).__name__}")


def _looks_like_order_payload(payload: Mapping[str, Any]) -> bool:
    return bool(_order_id(payload) and (payload.get("order_status") or payload.get("status")))


def _order_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or "")


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
    "IBKRBrokerEventClient",
    "IBKRBrokerEventSource",
    "InMemoryIBKRBrokerEventClient",
    "ibkr_order_update_to_broker_events",
]
