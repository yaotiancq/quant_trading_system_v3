"""Default data portal implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from qts.core import DataError
from qts.domain import Bar, BarTimeframe, FeatureFrame, Quote, normalize_symbol, normalize_timestamp
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
        feature_pipeline: FeaturePipeline | None = None,
        enforce_replay_bounds: bool = False,
    ) -> None:
        self.provider = provider
        self.symbols = [normalize_symbol(symbol) for symbol in symbols]
        self.start = normalize_timestamp(start, assume_utc_for_naive=True)
        self.end = normalize_timestamp(end, end_of_day=True, assume_utc_for_naive=True)
        self.timeframe = timeframe
        self.feature_pipeline = feature_pipeline
        self.enforce_replay_bounds = bool(enforce_replay_bounds)
        self._history = provider.get_history(self.symbols, self.start, self.end, timeframe)
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


def _latest_timestamp(left: datetime | None, right: datetime) -> datetime:
    return right if left is None or right > left else left


__all__ = ["DefaultDataPortal"]
