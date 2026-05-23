"""Market data interfaces, normalization, and local providers."""

from __future__ import annotations

from .alpaca import (
    ALPACA_BAR_TIMEFRAMES,
    BAR_FIELDNAMES,
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_OUTPUT_FILENAME_TEMPLATE,
    OUTPUT_FORMATS,
    SUPPORTED_ALPACA_BAR_TIMEFRAMES,
    AlpacaBarDownloadConfig,
    AlpacaBarDownloadResult,
    AlpacaDataTransport,
    AlpacaMarketDataClient,
    UrllibAlpacaDataTransport,
    download_alpaca_bars,
    download_alpaca_bars_to_csv,
    normalize_alpaca_bar_timeframe,
    normalize_output_format,
    resolve_alpaca_output_path,
    write_alpaca_bar_rows,
)
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
    "ALPACA_BAR_TIMEFRAMES",
    "AlpacaBarDownloadConfig",
    "AlpacaBarDownloadResult",
    "AlpacaDataTransport",
    "AlpacaMarketDataClient",
    "BAR_FIELDNAMES",
    "CSVBarProvider",
    "DEFAULT_OUTPUT_DIRECTORY",
    "DEFAULT_OUTPUT_FILENAME_TEMPLATE",
    "DataPortal",
    "DefaultDataPortal",
    "LocalParquetProvider",
    "MarketDataProvider",
    "OPTIONAL_BAR_COLUMNS",
    "OUTPUT_FORMATS",
    "REQUIRED_BAR_COLUMNS",
    "ReplayMarketDataProvider",
    "SUPPORTED_ALPACA_BAR_TIMEFRAMES",
    "UrllibAlpacaDataTransport",
    "download_alpaca_bars",
    "download_alpaca_bars_to_csv",
    "filter_bars",
    "normalize_alpaca_bar_timeframe",
    "normalize_output_format",
    "read_csv_rows",
    "resolve_alpaca_output_path",
    "row_to_bar",
    "rows_to_bars",
    "validate_bar_columns",
    "write_alpaca_bar_rows",
]
