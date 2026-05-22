"""Local market data providers."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from qts.core import DataError
from qts.domain import Bar, BarTimeframe, DataAdjustment, Quote, coerce_enum, normalize_symbol

from .normalization import filter_bars, read_csv_rows, rows_to_bars


class BaseHistoricalBarProvider:
    """Base provider backed by normalized in-memory bars."""

    def __init__(self, bars: Sequence[Bar]) -> None:
        self._bars = sorted(list(bars), key=lambda bar: (bar.timestamp, bar.symbol))
        self._latest_by_symbol: dict[str, Bar] = {}

    def get_history(
        self,
        symbols: Sequence[str],
        start: datetime | str,
        end: datetime | str,
        timeframe: BarTimeframe | str,
        adjustment: DataAdjustment | str = DataAdjustment.RAW,
    ) -> list[Bar]:
        if coerce_enum(DataAdjustment, adjustment) != DataAdjustment.RAW:
            raise DataError("only RAW data adjustment is supported in Phase 2")
        return filter_bars(self._bars, symbols=symbols, start=start, end=end, timeframe=timeframe)

    def iter_replay(
        self,
        symbols: Sequence[str],
        start: datetime | str,
        end: datetime | str,
        timeframe: BarTimeframe | str,
    ) -> Iterator[Bar]:
        for bar in self.get_history(symbols, start, end, timeframe):
            self._latest_by_symbol[bar.symbol] = bar
            yield bar

    def get_latest_bar(self, symbol: str) -> Bar | None:
        return self._latest_by_symbol.get(normalize_symbol(symbol))

    def get_latest_quote(self, symbol: str) -> Quote | None:
        return None

    def subscribe(
        self,
        symbols: Sequence[str],
        data_types: Sequence[str],
        callback: Callable[[Any], None],
    ) -> Any:
        raise DataError("live subscriptions are out of scope for Phase 2 local providers")

    def close(self) -> None:
        return None


class CSVBarProvider(BaseHistoricalBarProvider):
    """Historical bar provider backed by a local CSV file."""

    def __init__(
        self,
        path: str | Path,
        *,
        default_timeframe: BarTimeframe | str = BarTimeframe.MINUTE,
        source: str = "local_csv",
    ) -> None:
        self.path = Path(path)
        rows = read_csv_rows(self.path)
        super().__init__(rows_to_bars(rows, default_timeframe=default_timeframe, source=source))


class LocalParquetProvider(BaseHistoricalBarProvider):
    """Historical bar provider backed by a local Parquet file.

    This provider uses pandas or pyarrow when one is installed. The project keeps
    those dependencies optional in Phase 2 so CSV fixtures remain runnable in a
    minimal environment.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        default_timeframe: BarTimeframe | str = BarTimeframe.MINUTE,
        source: str = "local_parquet",
    ) -> None:
        self.path = Path(path)
        rows = _read_parquet_rows(self.path)
        super().__init__(rows_to_bars(rows, default_timeframe=default_timeframe, source=source))


class ReplayMarketDataProvider(BaseHistoricalBarProvider):
    """Deterministic replay provider backed by a preloaded bar sequence."""

    def __init__(self, bars: Sequence[Bar]) -> None:
        super().__init__(bars)


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise DataError(f"Parquet file does not exist: {path}")

    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        pd = None  # type: ignore[assignment]

    if pd is not None:
        frame = pd.read_parquet(path)
        return frame.to_dict(orient="records")

    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise DataError(
            "reading Parquet requires optional dependency pandas or pyarrow; "
            "CSV fixtures remain supported without third-party packages"
        ) from exc

    table = pq.read_table(path)
    return table.to_pylist()


__all__ = [
    "BaseHistoricalBarProvider",
    "CSVBarProvider",
    "LocalParquetProvider",
    "ReplayMarketDataProvider",
]
