"""Helpers for normalized broker order/fill event synchronization."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from qts.core import ConfigurationError, DataError
from qts.domain import (
    Account,
    BrokerEvent,
    BrokerEventType,
    Fill,
    Order,
    Position,
    normalize_timestamp,
)


BrokerEventHandler = Callable[[BrokerEvent], object]


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


@dataclass(frozen=True)
class BrokerEventSyncPolicy:
    """Fail-closed controls for broker-event lifecycle synchronization."""

    deduplicate: bool = True
    fail_on_out_of_order: bool = True
    max_gap_seconds: float | None = None
    fail_on_gap: bool = True

    def __post_init__(self) -> None:
        if self.max_gap_seconds is not None and self.max_gap_seconds < 0:
            raise ConfigurationError("broker event max_gap_seconds must be non-negative")


@dataclass
class BrokerEventSyncCheckpoint:
    """Restart-safe checkpoint for normalized broker-event processing."""

    last_event_timestamp: datetime | None = None
    processed_event_ids: set[str] = field(default_factory=set)
    processed_count: int = 0

    def __post_init__(self) -> None:
        if self.last_event_timestamp is not None:
            self.last_event_timestamp = normalize_timestamp(self.last_event_timestamp)
        self.processed_event_ids = {str(event_id) for event_id in self.processed_event_ids}

    def has_seen(self, event_id: str) -> bool:
        return event_id in self.processed_event_ids

    def remember(self, event: BrokerEvent) -> None:
        self.processed_event_ids.add(event.event_id)
        if self.last_event_timestamp is None:
            self.last_event_timestamp = event.timestamp
        else:
            self.last_event_timestamp = max(self.last_event_timestamp, event.timestamp)
        self.processed_count += 1

    def to_dict(self) -> dict[str, object]:
        timestamp = None
        if self.last_event_timestamp is not None:
            timestamp = self.last_event_timestamp.isoformat().replace("+00:00", "Z")
        return {
            "last_event_timestamp": timestamp,
            "processed_event_count": self.processed_count,
            "processed_event_id_count": len(self.processed_event_ids),
        }


@dataclass
class BrokerEventSyncResult:
    """Counters and status for one broker-event synchronization run."""

    processed_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    gap_count: int = 0
    out_of_order_count: int = 0
    last_event_timestamp: datetime | None = None
    closed: bool = False
    stopped_reason: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        timestamp = None
        if self.last_event_timestamp is not None:
            timestamp = self.last_event_timestamp.isoformat().replace("+00:00", "Z")
        return {
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "duplicate_count": self.duplicate_count,
            "gap_count": self.gap_count,
            "out_of_order_count": self.out_of_order_count,
            "last_event_timestamp": timestamp,
            "closed": self.closed,
            "stopped_reason": self.stopped_reason,
            "errors": list(self.errors),
        }


class BrokerEventSyncLoop:
    """Run broker events through idempotency, gap, and ordering checks."""

    def __init__(
        self,
        source: BrokerEventSource,
        handler: BrokerEventHandler,
        *,
        checkpoint: BrokerEventSyncCheckpoint | None = None,
        policy: BrokerEventSyncPolicy | None = None,
    ) -> None:
        self.source = source
        self.handler = handler
        self.checkpoint = checkpoint or BrokerEventSyncCheckpoint()
        self.policy = policy or BrokerEventSyncPolicy()

    def run(self, *, max_events: int = 0) -> BrokerEventSyncResult:
        if max_events < 0:
            raise ConfigurationError("max_events must be non-negative")
        result = BrokerEventSyncResult(
            last_event_timestamp=self.checkpoint.last_event_timestamp,
        )
        try:
            for event in self.source.iter_events():
                if self._is_duplicate(event):
                    result.duplicate_count += 1
                    result.skipped_count += 1
                    continue
                if self._is_out_of_order(event, result):
                    result.skipped_count += 1
                    continue
                self._validate_gap(event, result)
                self.handler(event)
                self.checkpoint.remember(event)
                result.processed_count += 1
                result.last_event_timestamp = self.checkpoint.last_event_timestamp
                if max_events and result.processed_count >= max_events:
                    result.stopped_reason = "max_events"
                    return result
            result.stopped_reason = "source_exhausted"
            return result
        except Exception as exc:
            result.errors.append(str(exc))
            raise
        finally:
            self.source.close()
            result.closed = True

    def _is_duplicate(self, event: BrokerEvent) -> bool:
        return self.policy.deduplicate and self.checkpoint.has_seen(event.event_id)

    def _is_out_of_order(
        self,
        event: BrokerEvent,
        result: BrokerEventSyncResult,
    ) -> bool:
        previous = self.checkpoint.last_event_timestamp
        if previous is None or event.timestamp >= previous:
            return False
        result.out_of_order_count += 1
        message = (
            f"out-of-order broker event {event.event_id}: "
            f"{event.timestamp.isoformat()} < {previous.isoformat()}"
        )
        if self.policy.fail_on_out_of_order:
            raise DataError(message)
        return True

    def _validate_gap(
        self,
        event: BrokerEvent,
        result: BrokerEventSyncResult,
    ) -> None:
        max_gap_seconds = self.policy.max_gap_seconds
        previous = self.checkpoint.last_event_timestamp
        if max_gap_seconds is None or previous is None or event.timestamp <= previous:
            return
        gap_seconds = (event.timestamp - previous).total_seconds()
        if gap_seconds <= max_gap_seconds:
            return
        result.gap_count += 1
        message = (
            f"broker event gap exceeded: gap_seconds={gap_seconds:.3f} "
            f"max_gap_seconds={max_gap_seconds:.3f}"
        )
        if self.policy.fail_on_gap:
            raise DataError(message)


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
    "BrokerEventHandler",
    "BrokerEventSource",
    "BrokerEventSyncCheckpoint",
    "BrokerEventSyncLoop",
    "BrokerEventSyncPolicy",
    "BrokerEventSyncResult",
    "InMemoryBrokerEventSource",
    "broker_event_from_account",
    "broker_event_from_fill",
    "broker_event_from_order",
    "broker_event_from_position",
    "broker_events_from_poll",
]
