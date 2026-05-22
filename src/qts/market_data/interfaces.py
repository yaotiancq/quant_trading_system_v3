"""Market data protocols."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from typing import Any, Protocol

from qts.domain import Bar, BarTimeframe, DataAdjustment, FeatureFrame, Quote


class MarketDataProvider(Protocol):
    """Normalized market data provider contract."""

    def get_history(
        self,
        symbols: Sequence[str],
        start: datetime | str,
        end: datetime | str,
        timeframe: BarTimeframe | str,
        adjustment: DataAdjustment | str = DataAdjustment.RAW,
    ) -> list[Bar]:
        """Return normalized historical bars."""

    def iter_replay(
        self,
        symbols: Sequence[str],
        start: datetime | str,
        end: datetime | str,
        timeframe: BarTimeframe | str,
    ) -> Iterator[Bar]:
        """Yield normalized market data events in deterministic order."""

    def get_latest_bar(self, symbol: str) -> Bar | None:
        """Return the latest known bar for a symbol."""

    def get_latest_quote(self, symbol: str) -> Quote | None:
        """Return the latest known quote for a symbol when available."""

    def subscribe(
        self,
        symbols: Sequence[str],
        data_types: Sequence[str],
        callback: Callable[[Any], None],
    ) -> Any:
        """Subscribe to live updates when supported."""

    def close(self) -> None:
        """Release provider resources."""


class DataPortal(Protocol):
    """Unified read interface for market data and computed features."""

    def get_bars(
        self,
        symbol: str,
        lookback: int | None = None,
        end: datetime | str | None = None,
    ) -> list[Bar]:
        """Return historical bars for one symbol."""

    def get_current_bar(self, symbol: str) -> Bar | None:
        """Return the current replay/live bar for one symbol."""

    def get_quote(self, symbol: str) -> Quote | None:
        """Return the latest quote for one symbol when available."""

    def get_feature_frame(
        self,
        symbols: Sequence[str],
        feature_names: Sequence[str] | None = None,
        lookback: int | None = None,
    ) -> FeatureFrame:
        """Return a feature frame for requested symbols."""

    def advance(self, market_event: Bar | Quote) -> None:
        """Update current data state."""


__all__ = ["DataPortal", "MarketDataProvider"]
