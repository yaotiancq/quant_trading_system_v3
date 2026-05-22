"""Market data interfaces, normalization, and local providers."""

from __future__ import annotations

from .interfaces import DataPortal, MarketDataProvider
from .normalization import (
    OPTIONAL_BAR_COLUMNS,
    REQUIRED_BAR_COLUMNS,
    filter_bars,
    read_csv_rows,
    row_to_bar,
    rows_to_bars,
    validate_bar_columns,
)
from .portal import DefaultDataPortal
from .providers import (
    BaseHistoricalBarProvider,
    CSVBarProvider,
    LocalParquetProvider,
    ReplayMarketDataProvider,
)

__all__ = [
    "BaseHistoricalBarProvider",
    "CSVBarProvider",
    "DataPortal",
    "DefaultDataPortal",
    "LocalParquetProvider",
    "MarketDataProvider",
    "OPTIONAL_BAR_COLUMNS",
    "REQUIRED_BAR_COLUMNS",
    "ReplayMarketDataProvider",
    "filter_bars",
    "read_csv_rows",
    "row_to_bar",
    "rows_to_bars",
    "validate_bar_columns",
]
