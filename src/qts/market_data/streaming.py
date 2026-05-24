"""Streaming market-data source adapters."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from qts.core import ConfigurationError, DataError
from qts.domain import Bar, BarTimeframe, Quote, RuntimeConfig, normalize_symbol, normalize_timestamp


ALPACA_STREAM_PROVIDERS = {"alpaca_stream", "alpaca_sip_stream", "alpaca_iex_stream"}
ALPACA_STREAM_FEEDS = {"iex", "sip"}
STREAM_EVENT_TYPES = {"bars", "quotes"}


class AlpacaStreamClient(Protocol):
    """Small Alpaca streaming client surface consumed by the adapter."""

    def connect(
        self,
        *,
        symbols: Sequence[str],
        event_types: Sequence[str],
        feed: str,
    ) -> None:
        """Connect and subscribe to requested stream channels."""

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        """Yield raw Alpaca stream payloads."""

    def close(self) -> None:
        """Release stream resources."""


@dataclass
class InMemoryAlpacaStreamClient:
    """Deterministic Alpaca-like stream client for tests and local smoke runs."""

    messages: Sequence[Mapping[str, Any] | Sequence[Mapping[str, Any]]]
    connected: bool = False
    closed: bool = False
    subscriptions: list[dict[str, object]] = field(default_factory=list)

    def connect(
        self,
        *,
        symbols: Sequence[str],
        event_types: Sequence[str],
        feed: str,
    ) -> None:
        self.connected = True
        self.closed = False
        self.subscriptions.append(
            {
                "symbols": [normalize_symbol(symbol) for symbol in symbols],
                "event_types": list(event_types),
                "feed": feed,
            }
        )

    def iter_messages(self) -> Iterator[Mapping[str, Any] | Sequence[Mapping[str, Any]]]:
        if not self.connected:
            raise DataError("Alpaca stream client is not connected")
        yield from self.messages

    def close(self) -> None:
        self.closed = True
        self.connected = False


class AlpacaStreamEventSource:
    """Convert Alpaca streaming payloads into normalized market events."""

    def __init__(
        self,
        client: AlpacaStreamClient,
        *,
        symbols: Sequence[str],
        event_types: Sequence[str],
        feed: str = "sip",
        source: str = "alpaca_stream",
        bar_timeframe: BarTimeframe | str = BarTimeframe.MINUTE,
    ) -> None:
        self.client = client
        self.symbols = [normalize_symbol(symbol) for symbol in symbols]
        if not self.symbols:
            raise ConfigurationError("Alpaca stream requires at least one symbol")
        self.event_types = normalize_stream_event_types(event_types)
        self.feed = normalize_alpaca_stream_feed(feed)
        self.source = source
        self.bar_timeframe = bar_timeframe
        self.closed = False

    def iter_events(self) -> Iterator[Bar | Quote]:
        self.client.connect(
            symbols=self.symbols,
            event_types=sorted(self.event_types),
            feed=self.feed,
        )
        for message in self.client.iter_messages():
            for payload in _iter_payloads(message):
                event = alpaca_stream_message_to_event(
                    payload,
                    source=self.source,
                    bar_timeframe=self.bar_timeframe,
                )
                if event is None:
                    continue
                if event.symbol not in self.symbols:
                    continue
                if _event_type_name(event) not in self.event_types:
                    continue
                yield event

    def close(self) -> None:
        self.client.close()
        self.closed = True


def alpaca_stream_event_source_from_config(
    config: RuntimeConfig,
    *,
    client: AlpacaStreamClient | None = None,
) -> AlpacaStreamEventSource:
    """Build an Alpaca stream event source from runtime market-data config."""
    market_data = config.market_data
    provider = str(market_data.get("provider") or "").strip().lower()
    if provider not in ALPACA_STREAM_PROVIDERS:
        raise ConfigurationError(f"unsupported Alpaca stream provider: {provider}")
    event_types = normalize_stream_event_types(market_data.get("event_types") or ["bars"])
    feed = normalize_alpaca_stream_feed(
        market_data.get("feed") or _feed_from_provider(provider)
    )
    symbols = market_data.get("symbols") or config.symbols
    if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes, bytearray)):
        raise ConfigurationError("market_data.symbols must be a list when configured")
    if client is None:
        mock_messages = market_data.get("mock_messages")
        if not isinstance(mock_messages, Sequence) or isinstance(
            mock_messages,
            (str, bytes, bytearray),
        ):
            raise ConfigurationError(
                "alpaca_stream requires an injected stream client or "
                "market_data.mock_messages; real websocket transport is not implemented"
            )
        client = InMemoryAlpacaStreamClient(mock_messages)
    return AlpacaStreamEventSource(
        client,
        symbols=[str(symbol) for symbol in symbols],
        event_types=sorted(event_types),
        feed=feed,
        source=provider,
        bar_timeframe=config.timeframe,
    )


def alpaca_stream_message_to_event(
    payload: Mapping[str, Any],
    *,
    source: str = "alpaca_stream",
    bar_timeframe: BarTimeframe | str = BarTimeframe.MINUTE,
) -> Bar | Quote | None:
    """Convert one Alpaca stream payload into a normalized event."""
    event_type = str(payload.get("T") or payload.get("type") or "").strip().lower()
    if event_type in {"success", "subscription"}:
        return None
    if event_type in {"error", "err"}:
        message = payload.get("msg") or payload.get("message") or payload
        raise DataError(f"Alpaca stream error payload: {message}")
    if event_type in {"b", "bar", "bars"}:
        return Bar(
            symbol=_required_text(payload, "S", "symbol"),
            timestamp=normalize_timestamp(_required_text(payload, "t", "timestamp")),
            timeframe=payload.get("timeframe") or bar_timeframe,
            open=float(_required_value(payload, "o", "open")),
            high=float(_required_value(payload, "h", "high")),
            low=float(_required_value(payload, "l", "low")),
            close=float(_required_value(payload, "c", "close")),
            volume=float(_required_value(payload, "v", "volume")),
            vwap=_optional_float(payload.get("vw") or payload.get("vwap")),
            trade_count=_optional_int(payload.get("n") or payload.get("trade_count")),
            source=source,
        )
    if event_type in {"q", "quote", "quotes"}:
        return Quote(
            symbol=_required_text(payload, "S", "symbol"),
            timestamp=normalize_timestamp(_required_text(payload, "t", "timestamp")),
            bid_price=float(_required_value(payload, "bp", "bid_price")),
            ask_price=float(_required_value(payload, "ap", "ask_price")),
            bid_size=_optional_float(payload.get("bs") or payload.get("bid_size")),
            ask_size=_optional_float(payload.get("as") or payload.get("ask_size")),
            source=source,
        )
    raise DataError(f"unsupported Alpaca stream event type: {event_type or '<missing>'}")


def normalize_stream_event_types(values: Sequence[Any]) -> set[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise ConfigurationError("market_data.event_types must be a list")
    normalized = {str(value).strip().lower() for value in values}
    normalized.discard("")
    unknown = sorted(normalized - STREAM_EVENT_TYPES)
    if unknown:
        raise ConfigurationError(
            f"unsupported market_data.event_types value(s): {', '.join(unknown)}"
        )
    if not normalized:
        raise ConfigurationError("market_data.event_types must not be empty")
    return normalized


def normalize_alpaca_stream_feed(value: Any) -> str:
    feed = str(value or "").strip().lower()
    if feed not in ALPACA_STREAM_FEEDS:
        allowed = ", ".join(sorted(ALPACA_STREAM_FEEDS))
        raise ConfigurationError(f"unsupported market_data.feed {value!r}; expected one of {allowed}")
    return feed


def _feed_from_provider(provider: str) -> str:
    if provider == "alpaca_iex_stream":
        return "iex"
    return "sip"


def _iter_payloads(
    message: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> Iterator[Mapping[str, Any]]:
    if isinstance(message, Mapping):
        yield message
        return
    if isinstance(message, Sequence) and not isinstance(message, (str, bytes, bytearray)):
        for payload in message:
            if not isinstance(payload, Mapping):
                raise DataError("Alpaca stream message list must contain mappings")
            yield payload
        return
    raise DataError(f"unsupported Alpaca stream message type: {type(message).__name__}")


def _event_type_name(event: Bar | Quote) -> str:
    return "bars" if isinstance(event, Bar) else "quotes"


def _required_text(payload: Mapping[str, Any], *keys: str) -> str:
    value = _required_value(payload, *keys)
    text = str(value).strip()
    if not text:
        raise DataError(f"missing required Alpaca stream field: {'/'.join(keys)}")
    return text


def _required_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    raise DataError(f"missing required Alpaca stream field: {'/'.join(keys)}")


def _optional_float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


__all__ = [
    "ALPACA_STREAM_FEEDS",
    "ALPACA_STREAM_PROVIDERS",
    "STREAM_EVENT_TYPES",
    "AlpacaStreamClient",
    "AlpacaStreamEventSource",
    "InMemoryAlpacaStreamClient",
    "alpaca_stream_event_source_from_config",
    "alpaca_stream_message_to_event",
    "normalize_alpaca_stream_feed",
    "normalize_stream_event_types",
]
