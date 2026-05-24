"""Alpaca historical stock bar download helpers."""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any, Protocol
from urllib import error, parse, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qts.calendar import MarketSessionConfig, MarketSessionService
from qts.core import ConfigurationError, DataError
from qts.domain import normalize_symbol, normalize_timestamp


ALPACA_BAR_TIMEFRAMES = {
    "1min": "1Min",
    "1m": "1Min",
    "1t": "1Min",
    "5min": "5Min",
    "5m": "5Min",
    "5t": "5Min",
    "15min": "15Min",
    "15m": "15Min",
    "15t": "15Min",
    "1hour": "1Hour",
    "1h": "1Hour",
    "1day": "1Day",
    "1d": "1Day",
}
SUPPORTED_ALPACA_BAR_TIMEFRAMES = ("1Min", "5Min", "15Min", "1Hour", "1Day")
OUTPUT_FORMATS = {"csv", "parquet"}
OUTPUT_LAYOUTS = {"partitioned", "single_file"}
PARTITION_FIELDS = {"alpaca_timeframe", "date", "source", "symbol", "timeframe"}
DEFAULT_OUTPUT_DIRECTORY = Path("data/alpaca")
DEFAULT_OUTPUT_FILENAME_TEMPLATE = "bars_{start}_{end}.{format}"
DEFAULT_PARTITION_BY = ("timeframe", "symbol", "date")
DEFAULT_SESSION_TIMEZONE = "America/New_York"
DEFAULT_SESSION_START = time(9, 30)
DEFAULT_SESSION_END = time(16, 0)
BAR_FIELDNAMES = [
    "symbol",
    "timestamp",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "trade_count",
    "source",
    "bar_interval",
    "alpaca_timeframe",
    "adjustment",
]


class AlpacaDataTransport(Protocol):
    """HTTP transport used by `AlpacaMarketDataClient`."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], str]:
        """Return status code, response headers, and decoded body text."""


class UrllibAlpacaDataTransport:
    """Dependency-free HTTP transport for Alpaca market data."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], str]:
        req = request.Request(url, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return response.status, dict(response.headers.items()), body
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, dict(exc.headers.items()), body
        except error.URLError as exc:
            raise DataError(f"could not reach Alpaca market data API: {exc.reason}") from exc


@dataclass(frozen=True)
class AlpacaSessionFilterConfig:
    """Local post-download session filter for Alpaca bar rows."""

    enabled: bool = True
    exchange: str = "XNYS"
    timezone: str = DEFAULT_SESSION_TIMEZONE
    start: time = DEFAULT_SESSION_START
    end: time = DEFAULT_SESSION_END
    calendar_provider: str = "builtin_us_equity"
    fail_closed: bool = True

    def applies_to_timeframe(self, timeframe: str) -> bool:
        return self.enabled and normalize_alpaca_bar_timeframe(timeframe) != "1Day"


@dataclass(frozen=True)
class AlpacaBarDownloadConfig:
    """Validated settings for one Alpaca historical bar download."""

    symbols: list[str]
    start: str
    end: str
    timeframe: str
    output_path: Path
    output_format: str = "csv"
    output_layout: str = "single_file"
    partition_by: tuple[str, ...] = ()
    filename_template: str = DEFAULT_OUTPUT_FILENAME_TEMPLATE
    session_filter: AlpacaSessionFilterConfig = field(default_factory=AlpacaSessionFilterConfig)
    feed: str = "sip"
    adjustment: str = "raw"
    sort: str = "asc"
    limit: int = 10000
    base_url: str = "https://data.alpaca.markets/v2"
    api_key_id: str | None = None
    secret_key: str | None = None

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        env_values: Mapping[str, str] | None = None,
    ) -> "AlpacaBarDownloadConfig":
        market_data = _mapping(raw.get("market_data"), "market_data")
        output = _mapping(raw.get("output"), "output")
        credentials = dict(_mapping(raw.get("credentials"), "credentials", required=False))
        env = os.environ if env_values is None else env_values

        provider = str(market_data.get("provider") or "").lower()
        if provider not in {"alpaca_sip", "alpaca_stock_bars", "alpaca_bars"}:
            raise ConfigurationError("market_data.provider must be alpaca_sip")

        symbols = [normalize_symbol(symbol) for symbol in list(market_data.get("symbols") or [])]
        if not symbols:
            raise ConfigurationError("market_data.symbols must be non-empty")

        base_url = str(market_data.get("base_url") or "").strip()
        base_url_env = market_data.get("base_url_env")
        if base_url_env:
            base_url = env.get(str(base_url_env), base_url)
        if not base_url:
            base_url = "https://data.alpaca.markets/v2"

        api_key_env = str(credentials.get("api_key_id_env") or "ALPACA_API_KEY_ID")
        secret_key_env = str(credentials.get("secret_key_env") or "ALPACA_SECRET_KEY")

        feed = str(market_data.get("feed") or "sip").lower()
        if feed != "sip":
            raise ConfigurationError("market_data.feed must be sip for Alpaca SIP downloads")

        start = _required_text(market_data.get("start"), "market_data.start")
        end = _required_text(market_data.get("end"), "market_data.end")
        timeframe = normalize_alpaca_bar_timeframe(
            _required_text(market_data.get("timeframe"), "market_data.timeframe")
        )
        session_filter = _session_filter_config(market_data.get("session_filter"))
        output_format = _configured_output_format(output)
        output_layout = _configured_output_layout(output)
        partition_by = _configured_partition_by(output, output_layout)
        filename_template = (
            _optional_text(output.get("filename_template")) or DEFAULT_OUTPUT_FILENAME_TEMPLATE
        )
        output_path = resolve_alpaca_output_path(
            output,
            symbols=symbols,
            start=start,
            end=end,
            timeframe=timeframe,
            feed=feed,
            adjustment=str(market_data.get("adjustment") or "raw").lower(),
            output_format=output_format,
            output_layout=output_layout,
            filename_template=filename_template,
        )

        return cls(
            symbols=symbols,
            start=start,
            end=end,
            timeframe=timeframe,
            output_path=output_path,
            output_format=output_format,
            output_layout=output_layout,
            partition_by=partition_by,
            filename_template=filename_template,
            session_filter=session_filter,
            feed=feed,
            adjustment=str(market_data.get("adjustment") or "raw").lower(),
            sort=str(market_data.get("sort") or "asc").lower(),
            limit=int(market_data.get("limit") or 10000),
            base_url=base_url,
            api_key_id=env.get(api_key_env),
            secret_key=env.get(secret_key_env),
        )

    def require_credentials(self) -> None:
        if not self.api_key_id or not self.secret_key:
            raise ConfigurationError(
                "Alpaca data download requires ALPACA_API_KEY_ID and ALPACA_SECRET_KEY"
            )


@dataclass(frozen=True)
class AlpacaBarDownloadResult:
    """Summary of a completed Alpaca bar download."""

    output_path: Path
    output_format: str
    output_layout: str
    symbols: list[str]
    timeframe: str
    feed: str
    row_count: int
    page_count: int
    output_file_count: int
    request_ids: list[str]
    raw_row_count: int = 0
    filtered_row_count: int = 0


class AlpacaMarketDataClient:
    """Small REST client for Alpaca historical stock bar data."""

    def __init__(
        self,
        *,
        base_url: str = "https://data.alpaca.markets/v2",
        api_key_id: str,
        secret_key: str,
        transport: AlpacaDataTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_id = api_key_id
        self.secret_key = secret_key
        self.transport = transport or UrllibAlpacaDataTransport()
        self.timeout = timeout

    def get_stock_bars_page(
        self,
        *,
        symbols: Sequence[str],
        timeframe: str,
        start: str,
        end: str,
        feed: str,
        adjustment: str,
        sort: str,
        limit: int,
        page_token: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        query = {
            "symbols": ",".join(normalize_symbol(symbol) for symbol in symbols),
            "timeframe": normalize_alpaca_bar_timeframe(timeframe),
            "start": _timestamp_text(start),
            "end": _timestamp_text(end),
            "feed": feed,
            "adjustment": adjustment,
            "sort": sort,
            "limit": str(limit),
            "page_token": page_token,
        }
        url = f"{self.base_url}/stocks/bars?{parse.urlencode(_without_empty_values(query))}"
        headers = {
            "Accept": "application/json",
            "APCA-API-KEY-ID": self.api_key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
        }
        status, response_headers, response_body = self.transport.request(
            "GET",
            url,
            headers=headers,
            timeout=self.timeout,
        )
        payload = _parse_json_response(response_body)
        if not 200 <= status < 300:
            raise DataError(_error_message(payload, status))
        if not isinstance(payload, dict):
            raise DataError("expected Alpaca bars response to be an object")
        return payload, _case_insensitive_get(response_headers, "X-Request-ID")


def download_alpaca_bars(
    config: AlpacaBarDownloadConfig,
    *,
    client: AlpacaMarketDataClient | None = None,
) -> AlpacaBarDownloadResult:
    """Download paginated Alpaca stock bars and write the configured output format."""
    config.require_credentials()
    data_client = client or AlpacaMarketDataClient(
        base_url=config.base_url,
        api_key_id=config.api_key_id or "",
        secret_key=config.secret_key or "",
    )
    output_path = config.output_path
    if config.output_layout == "partitioned":
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    request_ids: list[str] = []
    page_count = 0
    page_token: str | None = None
    while True:
        payload, request_id = data_client.get_stock_bars_page(
            symbols=config.symbols,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
            feed=config.feed,
            adjustment=config.adjustment,
            sort=config.sort,
            limit=config.limit,
            page_token=page_token,
        )
        page_count += 1
        if request_id:
            request_ids.append(request_id)
        rows.extend(_bars_payload_to_rows(payload, config))
        page_token = _optional_text(payload.get("next_page_token"))
        if not page_token:
            break

    raw_row_count = len(rows)
    rows = filter_alpaca_session_rows(
        rows,
        session_filter=config.session_filter,
        timeframe=config.timeframe,
    )
    filtered_row_count = raw_row_count - len(rows)
    rows.sort(key=lambda row: (str(row["timestamp"]), str(row["symbol"])))
    output_files = write_alpaca_bar_rows(
        output_path,
        rows,
        output_format=config.output_format,
        output_layout=config.output_layout,
        partition_by=config.partition_by,
        filename_template=config.filename_template,
        template_values=_output_template_values(
            symbols=config.symbols,
            start=config.start,
            end=config.end,
            timeframe=config.timeframe,
            feed=config.feed,
            adjustment=config.adjustment,
            output_format=config.output_format,
        ),
    )
    return AlpacaBarDownloadResult(
        output_path=output_path,
        output_format=config.output_format,
        output_layout=config.output_layout,
        symbols=list(config.symbols),
        timeframe=config.timeframe,
        feed=config.feed,
        row_count=len(rows),
        page_count=page_count,
        output_file_count=len(output_files),
        request_ids=request_ids,
        raw_row_count=raw_row_count,
        filtered_row_count=filtered_row_count,
    )


def download_alpaca_bars_to_csv(
    config: AlpacaBarDownloadConfig,
    *,
    client: AlpacaMarketDataClient | None = None,
) -> AlpacaBarDownloadResult:
    """Download paginated Alpaca stock bars and write normalized CSV rows."""
    csv_config = AlpacaBarDownloadConfig(
        symbols=config.symbols,
        start=config.start,
        end=config.end,
        timeframe=config.timeframe,
        output_path=config.output_path,
        output_format="csv",
        output_layout=config.output_layout,
        partition_by=config.partition_by,
        filename_template=config.filename_template,
        session_filter=config.session_filter,
        feed=config.feed,
        adjustment=config.adjustment,
        sort=config.sort,
        limit=config.limit,
        base_url=config.base_url,
        api_key_id=config.api_key_id,
        secret_key=config.secret_key,
    )
    return download_alpaca_bars(csv_config, client=client)


def normalize_alpaca_bar_timeframe(value: str) -> str:
    """Normalize supported user-facing K-line levels to Alpaca timeframes."""
    text = str(value).strip()
    if text in SUPPORTED_ALPACA_BAR_TIMEFRAMES:
        return text
    normalized = text.lower().replace(" ", "").replace("_", "")
    if normalized not in ALPACA_BAR_TIMEFRAMES:
        allowed = ", ".join(SUPPORTED_ALPACA_BAR_TIMEFRAMES)
        raise ConfigurationError(f"unsupported Alpaca bar timeframe {value!r}; expected one of {allowed}")
    return ALPACA_BAR_TIMEFRAMES[normalized]


def normalize_output_format(value: str) -> str:
    """Normalize downloader output format."""
    normalized = str(value).strip().lower()
    if normalized not in OUTPUT_FORMATS:
        allowed = ", ".join(sorted(OUTPUT_FORMATS))
        raise ConfigurationError(f"unsupported output.format {value!r}; expected one of {allowed}")
    return normalized


def normalize_output_layout(value: str) -> str:
    """Normalize downloader output layout."""
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in OUTPUT_LAYOUTS:
        allowed = ", ".join(sorted(OUTPUT_LAYOUTS))
        raise ConfigurationError(f"unsupported output.layout {value!r}; expected one of {allowed}")
    return normalized


def resolve_alpaca_output_path(
    output: Mapping[str, Any],
    *,
    symbols: Sequence[str],
    start: str,
    end: str,
    timeframe: str,
    feed: str,
    adjustment: str,
    output_format: str,
    output_layout: str,
    filename_template: str,
) -> Path:
    """Resolve a concrete downloader output path from path or filename templates."""
    normalized_format = normalize_output_format(output_format)
    normalized_layout = normalize_output_layout(output_layout)

    explicit_path = _optional_text(output.get("path"))
    directory_text = _optional_text(output.get("directory"))
    if normalized_layout == "partitioned":
        path = Path(explicit_path or directory_text or DEFAULT_OUTPUT_DIRECTORY)
        if path.suffix.lower().lstrip(".") in OUTPUT_FORMATS:
            raise ConfigurationError("partitioned output path must be a directory, not a file")
        return path

    template_values = _output_template_values(
        symbols=symbols,
        start=start,
        end=end,
        timeframe=timeframe,
        feed=feed,
        adjustment=adjustment,
        output_format=normalized_format,
    )
    directory = Path(directory_text) if directory_text else DEFAULT_OUTPUT_DIRECTORY
    if explicit_path:
        path = Path(_render_output_template(explicit_path, template_values, "output.path"))
    else:
        filename = _render_output_template(
            filename_template,
            template_values,
            "output.filename_template",
        )
        path = directory / filename

    _validate_output_path_extension(path, normalized_format)
    return path


def write_alpaca_bar_rows(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    output_format: str,
    output_layout: str = "single_file",
    partition_by: Sequence[str] = (),
    filename_template: str = DEFAULT_OUTPUT_FILENAME_TEMPLATE,
    template_values: Mapping[str, str] | None = None,
) -> list[Path]:
    """Write normalized Alpaca bar rows to CSV/Parquet and return written paths."""
    normalized_format = normalize_output_format(output_format)
    normalized_layout = normalize_output_layout(output_layout)
    if normalized_layout == "partitioned":
        return _write_partitioned_bar_rows(
            path,
            rows,
            output_format=normalized_format,
            partition_by=tuple(partition_by or DEFAULT_PARTITION_BY),
            filename_template=filename_template,
            template_values=template_values or {"format": normalized_format},
        )

    _validate_output_path_extension(path, normalized_format)
    if normalized_format == "csv":
        _write_bar_rows_csv(path, rows)
    else:
        _write_bar_rows_parquet(path, rows)
    return [path]


def filter_alpaca_session_rows(
    rows: Sequence[dict[str, Any]],
    *,
    session_filter: AlpacaSessionFilterConfig,
    timeframe: str,
) -> list[dict[str, Any]]:
    """Apply local regular-session filtering to normalized Alpaca bar rows."""
    if not session_filter.applies_to_timeframe(timeframe):
        return list(rows)
    session_service = MarketSessionService(
        MarketSessionConfig.from_mapping(
            {
                "exchange": session_filter.exchange,
                "timezone": session_filter.timezone,
                "regular_session_only": True,
                "extended_hours": {"enabled": False},
                "fail_closed": session_filter.fail_closed,
                "calendar_provider": session_filter.calendar_provider,
                "regular_open": session_filter.start.strftime("%H:%M"),
                "regular_close": session_filter.end.strftime("%H:%M"),
            }
        )
    )

    return [
        row
        for row in rows
        if session_service.is_regular_session(
            normalize_timestamp(row["timestamp"], assume_utc_for_naive=True)
        )
    ]


def _bars_payload_to_rows(
    payload: Mapping[str, Any],
    config: AlpacaBarDownloadConfig,
) -> list[dict[str, Any]]:
    bars = payload.get("bars")
    if isinstance(bars, Mapping):
        rows: list[dict[str, Any]] = []
        for symbol, symbol_bars in bars.items():
            if not isinstance(symbol_bars, list):
                raise DataError(f"expected bars for {symbol} to be a list")
            rows.extend(_bar_to_row(symbol, item, config) for item in symbol_bars)
        return rows
    if isinstance(bars, list):
        return [_bar_to_row(item.get("S") or item.get("symbol"), item, config) for item in bars]
    raise DataError("expected Alpaca bars response to include a bars mapping")


def _bar_to_row(symbol: Any, bar: Any, config: AlpacaBarDownloadConfig) -> dict[str, Any]:
    if not isinstance(bar, Mapping):
        raise DataError("expected Alpaca bar item to be an object")
    normalized_symbol = normalize_symbol(str(symbol or bar.get("symbol") or bar.get("S") or ""))
    timestamp = normalize_timestamp(_required_text(bar.get("t"), "bar.t"))
    return {
        "symbol": normalized_symbol,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "timeframe": _domain_timeframe(config.timeframe),
        "open": _required_number(bar.get("o"), "bar.o"),
        "high": _required_number(bar.get("h"), "bar.h"),
        "low": _required_number(bar.get("l"), "bar.l"),
        "close": _required_number(bar.get("c"), "bar.c"),
        "volume": _required_number(bar.get("v"), "bar.v"),
        "vwap": _optional_number(bar.get("vw")),
        "trade_count": _optional_int(bar.get("n")),
        "source": f"alpaca_{config.feed}_{config.timeframe}",
        "bar_interval": config.timeframe,
        "alpaca_timeframe": config.timeframe,
        "adjustment": _domain_adjustment(config.adjustment),
    }


def _write_bar_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BAR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in BAR_FIELDNAMES})


def _write_bar_rows_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    normalized_rows = [{key: row.get(key) for key in BAR_FIELDNAMES} for row in rows]
    pandas_error: Exception | None = None
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        pd = None  # type: ignore[assignment]

    if pd is not None:
        frame = pd.DataFrame(normalized_rows, columns=BAR_FIELDNAMES)
        try:
            frame.to_parquet(path, index=False)
            return
        except ImportError as exc:
            pandas_error = exc

    try:
        import pyarrow as pa  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise DataError(
            "writing Parquet requires optional dependency pandas or pyarrow; "
            "use output.format=csv or install the data extra"
        ) from pandas_error or exc

    table = pa.Table.from_pylist(normalized_rows)
    pq.write_table(table, path)


def _write_partitioned_bar_rows(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    output_format: str,
    partition_by: tuple[str, ...],
    filename_template: str,
    template_values: Mapping[str, str],
) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    if not rows:
        return []

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    group_values: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        row_values = _row_template_values(row)
        rendered_parts = tuple(
            f"{field}={_partition_path_token(_partition_value(row, field))}"
            for field in partition_by
        )
        grouped.setdefault(rendered_parts, []).append(row)
        group_values.setdefault(rendered_parts, {**template_values, **row_values})

    output_paths: list[Path] = []
    for rendered_parts, partition_rows in sorted(grouped.items()):
        partition_dir = root.joinpath(*rendered_parts)
        partition_dir.mkdir(parents=True, exist_ok=True)
        filename = _render_output_template(
            filename_template,
            group_values[rendered_parts],
            "output.filename_template",
        )
        output_path = partition_dir / filename
        _validate_output_path_extension(output_path, output_format)
        if output_format == "csv":
            _write_bar_rows_csv(output_path, partition_rows)
        else:
            _write_bar_rows_parquet(output_path, partition_rows)
        output_paths.append(output_path)
    return output_paths


def _domain_timeframe(alpaca_timeframe: str) -> str:
    if alpaca_timeframe.endswith("Min"):
        return "MINUTE"
    if alpaca_timeframe.endswith("Hour"):
        return "HOUR"
    return "DAY"


def _domain_adjustment(alpaca_adjustment: str) -> str:
    normalized = str(alpaca_adjustment).strip().lower().replace("-", "_")
    if normalized == "raw":
        return "RAW"
    if normalized in {"split", "split_adjusted"}:
        return "SPLIT_ADJUSTED"
    if normalized in {"dividend", "dividend_adjusted"}:
        return "DIVIDEND_ADJUSTED"
    if normalized in {"all", "total_return"}:
        return "TOTAL_RETURN"
    return normalized.upper()


def _configured_output_layout(output: Mapping[str, Any]) -> str:
    configured_layout = _optional_text(output.get("layout"))
    if configured_layout:
        return normalize_output_layout(configured_layout)
    if _optional_text(output.get("path")):
        return "single_file"
    return "partitioned"


def _session_filter_config(raw: Any) -> AlpacaSessionFilterConfig:
    if raw is None:
        return AlpacaSessionFilterConfig()
    if isinstance(raw, bool):
        return AlpacaSessionFilterConfig(enabled=raw)
    if isinstance(raw, str):
        text = raw.strip().lower().replace("-", "_")
        if text in {"regular", "regular_hours", "rth", "true", "enabled"}:
            return AlpacaSessionFilterConfig(enabled=True)
        if text in {"none", "off", "false", "disabled"}:
            return AlpacaSessionFilterConfig(enabled=False)
        raise ConfigurationError(
            "market_data.session_filter must be a mapping, regular, or disabled"
        )

    data = _mapping(raw, "market_data.session_filter")
    enabled = _optional_bool(data.get("enabled"), default=True)
    exchange = _optional_text(data.get("exchange")) or "XNYS"
    timezone = _optional_text(data.get("timezone")) or DEFAULT_SESSION_TIMEZONE
    start = _parse_session_time(data.get("start") or DEFAULT_SESSION_START, "session_filter.start")
    end = _parse_session_time(data.get("end") or DEFAULT_SESSION_END, "session_filter.end")
    calendar_provider = _optional_text(data.get("calendar_provider")) or "builtin_us_equity"
    fail_closed = _optional_bool(data.get("fail_closed"), default=True)
    if start == end:
        raise ConfigurationError("session_filter.start and session_filter.end must differ")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"unknown session filter timezone: {timezone}") from exc
    MarketSessionConfig.from_mapping(
        {
            "exchange": exchange,
            "timezone": timezone,
            "regular_session_only": True,
            "extended_hours": {"enabled": False},
            "fail_closed": fail_closed,
            "calendar_provider": calendar_provider,
            "regular_open": start.strftime("%H:%M"),
            "regular_close": end.strftime("%H:%M"),
        }
    )
    return AlpacaSessionFilterConfig(
        enabled=enabled,
        exchange=exchange,
        timezone=timezone,
        start=start,
        end=end,
        calendar_provider=calendar_provider,
        fail_closed=fail_closed,
    )


def _configured_partition_by(output: Mapping[str, Any], output_layout: str) -> tuple[str, ...]:
    normalized_layout = normalize_output_layout(output_layout)
    raw_partition_by = output.get("partition_by")
    if normalized_layout == "single_file":
        if raw_partition_by:
            raise ConfigurationError("output.partition_by is only valid for partitioned output")
        return ()

    if raw_partition_by is None:
        return DEFAULT_PARTITION_BY
    if isinstance(raw_partition_by, str):
        fields = [field.strip() for field in raw_partition_by.split(",") if field.strip()]
    elif isinstance(raw_partition_by, Sequence):
        fields = [str(field).strip() for field in raw_partition_by if str(field).strip()]
    else:
        raise ConfigurationError("output.partition_by must be a list or comma-separated string")
    if not fields:
        raise ConfigurationError("output.partition_by must include at least one field")
    return tuple(_normalize_partition_field(field) for field in fields)


def _configured_output_format(output: Mapping[str, Any]) -> str:
    configured_format = _optional_text(output.get("format"))
    if configured_format:
        return normalize_output_format(configured_format)
    inferred_format = _infer_output_format(output)
    return inferred_format or "csv"


def _infer_output_format(output: Mapping[str, Any]) -> str | None:
    if _optional_text(output.get("layout")) == "partitioned":
        return None
    for key in ("path", "filename_template"):
        raw_value = _optional_text(output.get(key))
        if not raw_value or "{format}" in raw_value:
            continue
        suffix = Path(raw_value).suffix.lower().lstrip(".")
        if suffix in OUTPUT_FORMATS:
            return suffix
    return None


def _normalize_partition_field(value: str) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized not in PARTITION_FIELDS:
        allowed = ", ".join(sorted(PARTITION_FIELDS))
        raise ConfigurationError(
            f"unsupported output.partition_by field {value!r}; expected one of {allowed}"
        )
    return normalized


def _output_template_values(
    *,
    symbols: Sequence[str],
    start: str,
    end: str,
    timeframe: str,
    feed: str,
    adjustment: str,
    output_format: str,
) -> dict[str, str]:
    symbol_token = "-".join(_filename_token(normalize_symbol(symbol)) for symbol in symbols)
    return {
        "symbol": symbol_token,
        "symbols": symbol_token,
        "start": _timestamp_filename_token(start),
        "end": _timestamp_filename_token(end),
        "timeframe": _filename_token(timeframe),
        "feed": _filename_token(feed),
        "adjustment": _filename_token(adjustment),
        "format": output_format,
    }


def _row_template_values(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "alpaca_timeframe": _filename_token(str(row.get("alpaca_timeframe") or "")),
        "date": _partition_value(row, "date"),
        "source": _filename_token(str(row.get("source") or "")),
        "symbol": _filename_token(str(row.get("symbol") or "")),
        "timeframe": _filename_token(_partition_value(row, "timeframe")),
    }


def _partition_value(row: Mapping[str, Any], field: str) -> str:
    normalized_field = _normalize_partition_field(field)
    if normalized_field == "date":
        return normalize_timestamp(row["timestamp"], assume_utc_for_naive=True).date().isoformat()
    if normalized_field == "timeframe":
        return str(row.get("alpaca_timeframe") or row.get("timeframe") or "")
    value = row.get(normalized_field)
    if value is None or value == "":
        raise DataError(f"cannot partition bar rows by missing field: {normalized_field}")
    return str(value)


def _render_output_template(
    template: str,
    values: Mapping[str, str],
    field_name: str,
) -> str:
    try:
        rendered = template.format_map(values)
    except KeyError as exc:
        allowed = ", ".join(sorted(values))
        raise ConfigurationError(
            f"unknown placeholder {{{exc.args[0]}}} in {field_name}; expected one of {allowed}"
        ) from exc
    except ValueError as exc:
        raise ConfigurationError(f"invalid template in {field_name}: {exc}") from exc
    if not rendered.strip():
        raise ConfigurationError(f"{field_name} rendered to an empty value")
    return rendered


def _validate_output_path_extension(path: Path, output_format: str) -> None:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in OUTPUT_FORMATS and suffix != output_format:
        raise ConfigurationError(
            f"output path extension .{suffix} does not match output.format {output_format!r}; "
            "use a matching extension or include {format} in the output template"
        )


def _timestamp_filename_token(value: str) -> str:
    timestamp = normalize_timestamp(value, assume_utc_for_naive=True)
    return timestamp.isoformat().replace("+00:00", "Z").replace("-", "").replace(":", "").lower()


def _filename_token(value: str) -> str:
    text = str(value).strip().lower()
    chars: list[str] = []
    previous_separator = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            previous_separator = False
        elif not previous_separator:
            chars.append("-")
            previous_separator = True
    return "".join(chars).strip("-") or "value"


def _partition_path_token(value: str) -> str:
    text = str(value).strip()
    chars: list[str] = []
    previous_separator = False
    for char in text:
        if char.isalnum() or char in {"_", "-", "."}:
            chars.append(char)
            previous_separator = False
        elif not previous_separator:
            chars.append("-")
            previous_separator = True
    return "".join(chars).strip("-") or "value"


def _parse_session_time(value: Any, field_name: str) -> time:
    if isinstance(value, time):
        return value
    text = _required_text(value, field_name)
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        raise ConfigurationError(f"{field_name} must use HH:MM or HH:MM:SS")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return time(hour, minute, second)
    except ValueError as exc:
        raise ConfigurationError(f"{field_name} must be a valid time") from exc


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    raise ConfigurationError(f"expected boolean value, got {value!r}")


def _timestamp_text(value: str) -> str:
    return normalize_timestamp(value, assume_utc_for_naive=True).isoformat().replace("+00:00", "Z")


def _parse_json_response(response_body: str) -> Any:
    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DataError("Alpaca market data response was not valid JSON") from exc


def _error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, Mapping):
        for key in ("message", "error", "detail"):
            if payload.get(key):
                return f"Alpaca market data API error {status_code}: {payload[key]}"
    return f"Alpaca market data API error {status_code}"


def _mapping(value: Any, name: str, *, required: bool = True) -> Mapping[str, Any]:
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def _required_text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ConfigurationError(f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_number(value: Any, field_name: str) -> float:
    if value is None or value == "":
        raise DataError(f"{field_name} is required")
    return float(value)


def _optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _csv_value(value: Any) -> Any:
    return "" if value is None else value


def _without_empty_values(query: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in query.items() if value is not None and value != ""}


def _case_insensitive_get(headers: Mapping[str, str], key: str) -> str | None:
    lowered = key.lower()
    for header_key, value in headers.items():
        if header_key.lower() == lowered:
            return value
    return None


__all__ = [
    "ALPACA_BAR_TIMEFRAMES",
    "BAR_FIELDNAMES",
    "DEFAULT_OUTPUT_DIRECTORY",
    "DEFAULT_OUTPUT_FILENAME_TEMPLATE",
    "DEFAULT_PARTITION_BY",
    "DEFAULT_SESSION_END",
    "DEFAULT_SESSION_START",
    "DEFAULT_SESSION_TIMEZONE",
    "OUTPUT_FORMATS",
    "OUTPUT_LAYOUTS",
    "PARTITION_FIELDS",
    "SUPPORTED_ALPACA_BAR_TIMEFRAMES",
    "AlpacaBarDownloadConfig",
    "AlpacaBarDownloadResult",
    "AlpacaDataTransport",
    "AlpacaMarketDataClient",
    "AlpacaSessionFilterConfig",
    "UrllibAlpacaDataTransport",
    "download_alpaca_bars",
    "download_alpaca_bars_to_csv",
    "filter_alpaca_session_rows",
    "normalize_alpaca_bar_timeframe",
    "normalize_output_layout",
    "normalize_output_format",
    "resolve_alpaca_output_path",
    "write_alpaca_bar_rows",
]
