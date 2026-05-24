"""Helpers for normalized broker order/fill event synchronization."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime
from typing import Protocol

from qts.domain import (
    Account,
    BrokerEvent,
    BrokerEventType,
    Fill,
    Order,
    Position,
    normalize_timestamp,
)


class BrokerEventSource(Protocol):
    """Finite or streaming source of normalized broker lifecycle events."""

    def iter_events(self) -> Iterator[BrokerEvent]:
        """Yield normalized broker events."""

    def close(self) -> None:
        """Release event-source resources."""


class InMemoryBrokerEventSource:
    """Deterministic broker-event source for tests and local smoke workflows."""

    def __init__(self, events: Iterable[BrokerEvent]) -> None:
        self.events = list(events)
        self.closed = False

    def iter_events(self) -> Iterator[BrokerEvent]:
        yield from self.events

    def close(self) -> None:
        self.closed = True


def broker_event_from_order(order: Order, *, source: str = "broker_poll") -> BrokerEvent:
    """Build a stable event from a normalized broker order update."""
    timestamp = order.updated_at or order.created_at
    suffix = _event_timestamp(timestamp)
    event_id = (
        f"order:{order.order_id}:{order.status.value}:"
        f"{_quantity_key(order.filled_quantity)}:{_quantity_key(order.remaining_quantity)}:{suffix}"
    )
    return BrokerEvent(
        event_id=event_id,
        event_type=BrokerEventType.ORDER_UPDATE,
        timestamp=timestamp,
        source=source,
        order=order,
    )


def broker_event_from_fill(fill: Fill, *, source: str | None = None) -> BrokerEvent:
    """Build a stable event from a normalized broker fill."""
    event_source = source or fill.source
    return BrokerEvent(
        event_id=f"fill:{fill.fill_id}",
        event_type=BrokerEventType.FILL,
        timestamp=fill.timestamp,
        source=event_source,
        fill=fill,
    )


def broker_event_from_account(
    account: Account,
    *,
    source: str = "broker_poll",
) -> BrokerEvent:
    return BrokerEvent(
        event_id=f"account:{account.account_id or 'unknown'}:{_event_timestamp(account.timestamp)}",
        event_type=BrokerEventType.ACCOUNT_UPDATE,
        timestamp=account.timestamp,
        source=source,
        account=account,
    )


def broker_event_from_position(
    position: Position,
    *,
    source: str = "broker_poll",
) -> BrokerEvent:
    return BrokerEvent(
        event_id=f"position:{position.symbol}:{_event_timestamp(position.updated_at)}",
        event_type=BrokerEventType.POSITION_UPDATE,
        timestamp=position.updated_at,
        source=source,
        position=position,
    )


def broker_events_from_poll(
    *,
    orders: Sequence[Order] = (),
    fills: Sequence[Fill] = (),
    source: str = "broker_poll",
) -> list[BrokerEvent]:
    """Convert polling results into normalized broker events."""
    events = [broker_event_from_order(order, source=source) for order in orders]
    events.extend(broker_event_from_fill(fill, source=source) for fill in fills)
    return sorted(events, key=lambda event: (_event_priority(event), event.timestamp, event.event_id))


def _event_timestamp(timestamp: datetime) -> str:
    return normalize_timestamp(timestamp).isoformat().replace("+00:00", "Z")


def _quantity_key(value: float | int | None) -> str:
    if value is None:
        return "none"
    return f"{float(value):.12g}"


def _event_priority(event: BrokerEvent) -> int:
    if event.event_type == BrokerEventType.FILL:
        return 0
    if event.event_type == BrokerEventType.ORDER_UPDATE:
        return 1
    return 2


__all__ = [
    "BrokerEventSource",
    "InMemoryBrokerEventSource",
    "broker_event_from_account",
    "broker_event_from_fill",
    "broker_event_from_order",
    "broker_event_from_position",
    "broker_events_from_poll",
]
