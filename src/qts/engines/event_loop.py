"""Deterministic runtime market-event loop primitives."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from qts.calendar import MarketSessionService
from qts.core import Clock, ConfigurationError, DataError
from qts.domain import Bar, BarTimeframe, Quote, normalize_timestamp


MarketEvent = Bar | Quote
MarketEventHandler = Callable[[MarketEvent], object]


class MarketEventSource(Protocol):
    """Finite or streaming source of normalized market events."""

    def iter_events(self) -> Iterator[MarketEvent]:
        """Yield normalized market events."""

    def close(self) -> None:
        """Release any provider resources."""


@dataclass
class RuntimeEventLoopResult:
    """Execution counters for one runtime event-loop run."""

    processed_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    last_event_timestamp: datetime | None = None
    closed: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        last_timestamp = None
        if self.last_event_timestamp is not None:
            last_timestamp = self.last_event_timestamp.isoformat().replace("+00:00", "Z")
        return {
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "duplicate_count": self.duplicate_count,
            "last_event_timestamp": last_timestamp,
            "closed": self.closed,
            "errors": list(self.errors),
        }


class InMemoryMarketEventSource:
    """Deterministic market-event source for tests and local paper dry runs."""

    def __init__(self, events: Iterable[MarketEvent | Mapping[str, Any]]) -> None:
        self.events = [_coerce_market_event(event) for event in events]
        self.closed = False

    def iter_events(self) -> Iterator[MarketEvent]:
        yield from self.events

    def close(self) -> None:
        self.closed = True


class RuntimeEventLoop:
    """Run a market-event source through runtime safety checks and dispatch."""

    def __init__(
        self,
        source: MarketEventSource,
        handler: MarketEventHandler,
        *,
        session_service: MarketSessionService | None = None,
        clock: Clock | None = None,
        max_staleness_seconds: float | int | None = None,
        session_filter_enabled: bool = True,
        fail_on_out_of_order: bool = True,
        deduplicate: bool = True,
    ) -> None:
        self.source = source
        self.handler = handler
        self.session_service = session_service
        self.clock = clock
        self.max_staleness_seconds = _optional_non_negative(
            max_staleness_seconds,
            "max_staleness_seconds",
        )
        self.session_filter_enabled = session_filter_enabled
        self.fail_on_out_of_order = fail_on_out_of_order
        self.deduplicate = deduplicate
        self._seen_event_keys: set[tuple[object, ...]] = set()
        self._last_timestamp_by_symbol: dict[str, datetime] = {}

    def run(self, *, max_events: int = 0) -> RuntimeEventLoopResult:
        """Dispatch events until the source ends or max_events is reached."""
        if max_events < 0:
            raise ConfigurationError("max_events must be non-negative")
        result = RuntimeEventLoopResult()
        try:
            for event in self.source.iter_events():
                if self._is_duplicate(event):
                    result.duplicate_count += 1
                    result.skipped_count += 1
                    continue
                if self._is_outside_session(event):
                    result.skipped_count += 1
                    continue
                self._validate_ordering(event)
                self._validate_freshness(event)
                self.handler(event)
                result.processed_count += 1
                result.last_event_timestamp = event.timestamp
                if max_events and result.processed_count >= max_events:
                    break
        except Exception as exc:
            result.errors.append(str(exc))
            raise
        finally:
            self.source.close()
            result.closed = True
        return result

    def _is_duplicate(self, event: MarketEvent) -> bool:
        if not self.deduplicate:
            return False
        key = _event_key(event)
        if key in self._seen_event_keys:
            return True
        self._seen_event_keys.add(key)
        return False

    def _is_outside_session(self, event: MarketEvent) -> bool:
        if self.session_service is None or not self.session_filter_enabled:
            return False
        return not self.session_service.is_tradable(event.timestamp)

    def _validate_ordering(self, event: MarketEvent) -> None:
        previous = self._last_timestamp_by_symbol.get(event.symbol)
        if previous is not None and event.timestamp < previous:
            message = (
                f"out-of-order market event for {event.symbol}: "
                f"{event.timestamp.isoformat()} < {previous.isoformat()}"
            )
            if self.fail_on_out_of_order:
                raise DataError(message)
        self._last_timestamp_by_symbol[event.symbol] = max(previous or event.timestamp, event.timestamp)

    def _validate_freshness(self, event: MarketEvent) -> None:
        if self.clock is None or self.max_staleness_seconds is None:
            return
        age_seconds = (self.clock.now() - event.timestamp).total_seconds()
        if age_seconds > self.max_staleness_seconds:
            raise DataError(
                f"stale market event for {event.symbol}: age_seconds={age_seconds:.3f} "
                f"exceeds max_staleness_seconds={self.max_staleness_seconds:.3f}"
            )


def _coerce_market_event(raw: MarketEvent | Mapping[str, Any]) -> MarketEvent:
    if isinstance(raw, (Bar, Quote)):
        return raw
    if not isinstance(raw, Mapping):
        raise DataError(f"market event must be a Bar, Quote, or mapping; got {type(raw).__name__}")
    event_type = str(raw.get("type") or raw.get("event_type") or "").strip().lower()
    try:
        if event_type == "bar":
            return Bar(
                symbol=str(raw["symbol"]),
                timestamp=normalize_timestamp(raw["timestamp"]),
                timeframe=raw.get("timeframe", BarTimeframe.MINUTE),
                open=float(raw["open"]),
                high=float(raw["high"]),
                low=float(raw["low"]),
                close=float(raw["close"]),
                volume=float(raw["volume"]),
                vwap=_optional_float(raw.get("vwap")),
                trade_count=_optional_int(raw.get("trade_count")),
                source=_optional_text(raw.get("source")) or "fake_stream",
                bar_interval=_optional_text(raw.get("bar_interval")),
                adjustment=raw.get("adjustment", "RAW"),
            )
        if event_type == "quote":
            return Quote(
                symbol=str(raw["symbol"]),
                timestamp=normalize_timestamp(raw["timestamp"]),
                bid_price=float(raw["bid_price"]),
                ask_price=float(raw["ask_price"]),
                bid_size=_optional_float(raw.get("bid_size")),
                ask_size=_optional_float(raw.get("ask_size")),
                source=_optional_text(raw.get("source")) or "fake_stream",
            )
    except KeyError as exc:
        raise DataError(f"missing market event field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise DataError(f"invalid market event: {exc}") from exc
    raise DataError("market event mapping requires type=bar or type=quote")


def _event_key(event: MarketEvent) -> tuple[object, ...]:
    if isinstance(event, Bar):
        return ("bar", event.symbol, event.timestamp, event.timeframe.value)
    return ("quote", event.symbol, event.timestamp, event.bid_price, event.ask_price)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_non_negative(value: float | int | None, field_name: str) -> float | None:
    if value is None:
        return None
    coerced = float(value)
    if coerced < 0:
        raise ConfigurationError(f"{field_name} must be non-negative")
    return coerced


def event_source_from_market_data_config(config: Mapping[str, Any]) -> InMemoryMarketEventSource:
    """Build the Phase B1 fake stream from runtime market_data config."""
    events = config.get("events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes, bytearray)):
        raise ConfigurationError("market_data.events must be a list when provider=fake_stream")
    return InMemoryMarketEventSource(events)


__all__ = [
    "InMemoryMarketEventSource",
    "MarketEvent",
    "MarketEventHandler",
    "MarketEventSource",
    "RuntimeEventLoop",
    "RuntimeEventLoopResult",
    "event_source_from_market_data_config",
]
