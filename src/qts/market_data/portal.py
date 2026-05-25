"""Default data portal implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from qts.core import ConfigurationError, DataError
from qts.domain import (
    Bar,
    BarTimeframe,
    DataAdjustment,
    FeatureFrame,
    Quote,
    normalize_symbol,
    normalize_timestamp,
)
from qts.features import FeaturePipeline

from .interfaces import MarketDataProvider


class DefaultDataPortal:
    """Small in-memory data portal for replay/research access."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        symbols: Sequence[str],
        start: datetime | str,
        end: datetime | str,
        timeframe: BarTimeframe | str = BarTimeframe.MINUTE,
        adjustment: DataAdjustment | str = DataAdjustment.RAW,
        bar_interval: str | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        enforce_replay_bounds: bool = False,
    ) -> None:
        self.provider = provider
        self.symbols = [normalize_symbol(symbol) for symbol in symbols]
        self.start = normalize_timestamp(start, assume_utc_for_naive=True)
        self.end = normalize_timestamp(end, end_of_day=True, assume_utc_for_naive=True)
        self.timeframe = timeframe
        self.adjustment = adjustment
        self.bar_interval = bar_interval
        self.feature_pipeline = feature_pipeline
        self.enforce_replay_bounds = bool(enforce_replay_bounds)
        self._history = provider.get_history(
            self.symbols,
            self.start,
            self.end,
            timeframe,
            adjustment=adjustment,
            bar_interval=bar_interval,
        )
        self._current_bars: dict[str, Bar] = {}
        self._current_quotes: dict[str, Quote] = {}
        self._visible_until: datetime | None = None

    def get_bars(
        self,
        symbol: str,
        lookback: int | None = None,
        end: datetime | str | None = None,
    ) -> list[Bar]:
        wanted_symbol = normalize_symbol(symbol)
        end_ts = self._bounded_end(end)
        if self.enforce_replay_bounds and end_ts is None:
            return []
        bars = [bar for bar in self._history if bar.symbol == wanted_symbol]
        if end_ts is not None:
            bars = [bar for bar in bars if bar.timestamp <= end_ts]
        if lookback is not None:
            if lookback <= 0:
                raise DataError("lookback must be positive")
            bars = bars[-lookback:]
        return bars

    def get_current_bar(self, symbol: str) -> Bar | None:
        return self._current_bars.get(normalize_symbol(symbol))

    def get_quote(self, symbol: str) -> Quote | None:
        return self._current_quotes.get(normalize_symbol(symbol)) or self.provider.get_latest_quote(symbol)

    def get_feature_frame(
        self,
        symbols: Sequence[str],
        feature_names: Sequence[str] | None = None,
        lookback: int | None = None,
    ) -> FeatureFrame:
        if self.feature_pipeline is None:
            raise DataError("feature pipeline is not configured")
        bars: list[Bar] = []
        for symbol in symbols:
            bars.extend(self.get_bars(symbol, lookback=lookback))
        frame = self.feature_pipeline.transform_batch(bars)
        if feature_names is None:
            return frame

        allowed = set(feature_names)
        filtered_rows = []
        for row in frame.features:
            filtered = {
                key: value
                for key, value in row.items()
                if key in allowed or key in {"symbol", "timestamp"}
            }
            filtered_rows.append(filtered)
        return FeatureFrame(
            symbols=frame.symbols,
            timestamps=frame.timestamps,
            features=filtered_rows,
            schema_version=frame.schema_version,
            generated_at=frame.generated_at,
            source=frame.source,
        )

    def advance(self, market_event: Bar | Quote) -> None:
        if isinstance(market_event, Bar):
            self._current_bars[market_event.symbol] = market_event
            self._visible_until = _latest_timestamp(self._visible_until, market_event.timestamp)
        elif isinstance(market_event, Quote):
            self._current_quotes[market_event.symbol] = market_event
            self._visible_until = _latest_timestamp(self._visible_until, market_event.timestamp)
        else:
            raise DataError(f"unsupported market event: {type(market_event).__name__}")

    def _bounded_end(self, end: datetime | str | None) -> datetime | None:
        requested_end = (
            normalize_timestamp(end, assume_utc_for_naive=True) if end is not None else None
        )
        if not self.enforce_replay_bounds:
            return requested_end
        if self._visible_until is None:
            return None
        if requested_end is None or requested_end > self._visible_until:
            return self._visible_until
        return requested_end


class InMemoryRuntimeDataPortal:
    """In-memory data portal for externally supplied runtime market events."""

    def __init__(
        self,
        *,
        feature_pipeline: FeaturePipeline | None = None,
        max_bars_per_symbol: int | None = None,
    ) -> None:
        if max_bars_per_symbol is not None and max_bars_per_symbol <= 0:
            raise ConfigurationError("max_bars_per_symbol must be a positive integer or None")
        self.feature_pipeline = feature_pipeline
        self.max_bars_per_symbol = max_bars_per_symbol
        self._bars: list[Bar] = []
        self._bars_by_symbol: dict[str, list[Bar]] = {}
        self._current_bars: dict[str, Bar] = {}
        self._quotes: dict[str, Quote] = {}

    def get_bars(
        self,
        symbol: str,
        lookback: int | None = None,
        end: datetime | str | None = None,
    ) -> list[Bar]:
        if lookback is not None and lookback <= 0:
            raise DataError("lookback must be positive")
        normalized_symbol = normalize_symbol(symbol)
        rows = list(self._bars_by_symbol.get(normalized_symbol, []))
        if end is not None:
            end_ts = normalize_timestamp(end)
            rows = [bar for bar in rows if bar.timestamp <= end_ts]
        return rows[-lookback:] if lookback is not None else rows

    def get_current_bar(self, symbol: str) -> Bar | None:
        return self._current_bars.get(normalize_symbol(symbol))

    def get_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(normalize_symbol(symbol))

    def get_feature_frame(
        self,
        symbols: Sequence[str],
        feature_names: Sequence[str] | None = None,
        lookback: int | None = None,
    ) -> FeatureFrame:
        if lookback is not None and lookback <= 0:
            raise DataError("lookback must be positive")
        if self.feature_pipeline is None:
            raise DataError("runtime data portal has no feature pipeline")
        wanted_symbols = {normalize_symbol(symbol) for symbol in symbols}
        bars = [bar for bar in self._bars if bar.symbol in wanted_symbols]
        if lookback is not None:
            bars = bars[-lookback:]
        return _filter_feature_frame(
            self.feature_pipeline.transform_batch(bars),
            feature_names,
        )

    def advance(self, market_event: Bar | Quote) -> None:
        symbol = normalize_symbol(market_event.symbol)
        if isinstance(market_event, Bar):
            self._append_bar(symbol, market_event)
            self._current_bars[symbol] = market_event
            return
        if isinstance(market_event, Quote):
            self._quotes[symbol] = market_event
            return
        raise DataError(f"unsupported market event: {type(market_event).__name__}")

    def _append_bar(self, symbol: str, bar: Bar) -> None:
        self._bars.append(bar)
        symbol_bars = self._bars_by_symbol.setdefault(symbol, [])
        symbol_bars.append(bar)
        if self.max_bars_per_symbol is None:
            return
        while len(symbol_bars) > self.max_bars_per_symbol:
            removed = symbol_bars.pop(0)
            self._bars.remove(removed)


def _filter_feature_frame(
    frame: FeatureFrame,
    feature_names: Sequence[str] | None,
) -> FeatureFrame:
    if feature_names is None:
        return frame
    allowed = set(feature_names)
    filtered_rows = [
        {
            key: value
            for key, value in row.items()
            if key in allowed or key in {"symbol", "timestamp"}
        }
        for row in frame.features
    ]
    return FeatureFrame(
        symbols=frame.symbols,
        timestamps=frame.timestamps,
        features=filtered_rows,
        schema_version=frame.schema_version,
        generated_at=frame.generated_at,
        source=frame.source,
    )


def _latest_timestamp(left: datetime | None, right: datetime) -> datetime:
    return right if left is None or right > left else left


__all__ = ["DefaultDataPortal", "InMemoryRuntimeDataPortal"]
