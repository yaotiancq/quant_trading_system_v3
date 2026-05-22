"""Market data normalization helpers."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from qts.core import DataError
from qts.domain import Bar, BarTimeframe, coerce_enum, normalize_symbol, normalize_timestamp


REQUIRED_BAR_COLUMNS = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
OPTIONAL_BAR_COLUMNS = {"timeframe", "vwap", "trade_count", "source"}


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataError(f"CSV file does not exist: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DataError(f"CSV file has no header: {csv_path}")
        rows = [dict(row) for row in reader]
    return rows


def rows_to_bars(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_timeframe: BarTimeframe | str,
    source: str | None = None,
) -> list[Bar]:
    bars: list[Bar] = []
    seen: set[tuple[str, datetime, BarTimeframe]] = set()
    for row_index, row in enumerate(rows, start=1):
        validate_bar_columns(row, row_index=row_index)
        bar = row_to_bar(row, default_timeframe=default_timeframe, source=source)
        key = (bar.symbol, bar.timestamp, bar.timeframe)
        if key in seen:
            raise DataError(
                f"duplicate bar for {bar.symbol} at {bar.timestamp.isoformat()} "
                f"with timeframe {bar.timeframe.value}"
            )
        seen.add(key)
        bars.append(bar)
    return sorted(bars, key=lambda bar: (bar.timestamp, bar.symbol))


def row_to_bar(
    row: Mapping[str, Any],
    *,
    default_timeframe: BarTimeframe | str,
    source: str | None = None,
) -> Bar:
    timeframe = row.get("timeframe") or default_timeframe
    try:
        return Bar(
            symbol=str(row["symbol"]),
            timestamp=normalize_timestamp(row["timestamp"]),
            timeframe=coerce_enum(BarTimeframe, timeframe),
            open=_to_float(row["open"], "open"),
            high=_to_float(row["high"], "high"),
            low=_to_float(row["low"], "low"),
            close=_to_float(row["close"], "close"),
            volume=_to_float(row["volume"], "volume"),
            vwap=_optional_float(row.get("vwap"), "vwap"),
            trade_count=_optional_int(row.get("trade_count"), "trade_count"),
            source=str(row.get("source") or source or "local"),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise DataError(f"invalid bar row for {row.get('symbol', '<unknown>')}: {exc}") from exc


def validate_bar_columns(row: Mapping[str, Any], *, row_index: int | None = None) -> None:
    missing = [column for column in sorted(REQUIRED_BAR_COLUMNS) if column not in row]
    if missing:
        location = f" on row {row_index}" if row_index is not None else ""
        raise DataError(f"missing required bar columns{location}: {', '.join(missing)}")


def filter_bars(
    bars: Iterable[Bar],
    *,
    symbols: Sequence[str],
    start: datetime | str,
    end: datetime | str,
    timeframe: BarTimeframe | str,
) -> list[Bar]:
    wanted_symbols = {normalize_symbol(symbol) for symbol in symbols}
    if not wanted_symbols:
        raise DataError("at least one symbol is required")
    start_ts = normalize_timestamp(start, assume_utc_for_naive=True)
    end_ts = normalize_timestamp(end, end_of_day=True, assume_utc_for_naive=True)
    wanted_timeframe = coerce_enum(BarTimeframe, timeframe)
    if end_ts < start_ts:
        raise DataError("end must be greater than or equal to start")

    filtered = [
        bar
        for bar in bars
        if bar.symbol in wanted_symbols
        and bar.timeframe == wanted_timeframe
        and start_ts <= bar.timestamp <= end_ts
    ]
    return sorted(filtered, key=lambda bar: (bar.timestamp, bar.symbol))


def _to_float(value: Any, field_name: str) -> float:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")
    return float(value)


def _optional_float(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


__all__ = [
    "OPTIONAL_BAR_COLUMNS",
    "REQUIRED_BAR_COLUMNS",
    "filter_bars",
    "read_csv_rows",
    "row_to_bar",
    "rows_to_bars",
    "validate_bar_columns",
]
