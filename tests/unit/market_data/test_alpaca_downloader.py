from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from urllib import parse

from qts.core import ConfigurationError
from qts.market_data import (
    AlpacaBarDownloadConfig,
    AlpacaMarketDataClient,
    CSVBarProvider,
    LocalParquetProvider,
    download_alpaca_bars,
    download_alpaca_bars_to_csv,
    normalize_alpaca_bar_timeframe,
)


class FakeTransport:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = list(pages)
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], str]:
        self.calls.append({"method": method, "url": url, "headers": dict(headers)})
        return 200, {"X-Request-ID": f"request-{len(self.calls)}"}, json.dumps(self.pages.pop(0))


def parquet_write_read_available() -> bool:
    return importlib.util.find_spec("pyarrow") is not None or (
        importlib.util.find_spec("pandas") is not None
        and importlib.util.find_spec("fastparquet") is not None
    )


class AlpacaDownloaderTests(unittest.TestCase):
    def test_normalizes_supported_kline_levels(self) -> None:
        self.assertEqual(normalize_alpaca_bar_timeframe("1min"), "1Min")
        self.assertEqual(normalize_alpaca_bar_timeframe("5MIN"), "5Min")
        self.assertEqual(normalize_alpaca_bar_timeframe("15m"), "15Min")
        self.assertEqual(normalize_alpaca_bar_timeframe("1hour"), "1Hour")
        self.assertEqual(normalize_alpaca_bar_timeframe("1day"), "1Day")

        with self.assertRaises(ConfigurationError):
            normalize_alpaca_bar_timeframe("30sec")

    def test_downloads_paginated_alpaca_bars_to_csv_compatible_with_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "bars.csv"
            config = AlpacaBarDownloadConfig(
                symbols=["SPY"],
                start="2024-01-02T14:30:00Z",
                end="2024-01-02T14:35:00Z",
                timeframe="5Min",
                feed="sip",
                output_path=output_path,
                api_key_id="key",
                secret_key="secret",
                base_url="https://data.alpaca.test/v2",
            )
            transport = FakeTransport(
                [
                    {
                        "bars": {
                            "SPY": [
                                {
                                    "t": "2024-01-02T14:30:00Z",
                                    "o": 100,
                                    "h": 101,
                                    "l": 99,
                                    "c": 100.5,
                                    "v": 1000,
                                    "n": 12,
                                    "vw": 100.2,
                                }
                            ]
                        },
                        "next_page_token": "next-page",
                    },
                    {
                        "bars": {
                            "SPY": [
                                {
                                    "t": "2024-01-02T14:35:00Z",
                                    "o": 100.5,
                                    "h": 102,
                                    "l": 100,
                                    "c": 101,
                                    "v": 1500,
                                    "n": 14,
                                    "vw": 101.1,
                                }
                            ]
                        }
                    },
                ]
            )
            client = AlpacaMarketDataClient(
                base_url=config.base_url,
                api_key_id="key",
                secret_key="secret",
                transport=transport,
            )

            result = download_alpaca_bars_to_csv(config, client=client)

            self.assertEqual(result.row_count, 2)
            self.assertEqual(result.page_count, 2)
            self.assertEqual(result.request_ids, ["request-1", "request-2"])
            provider = CSVBarProvider(output_path)
            bars = provider.get_history(
                ["SPY"],
                "2024-01-02T14:30:00Z",
                "2024-01-02T14:35:00Z",
                "MINUTE",
            )
            self.assertEqual(len(bars), 2)
            self.assertEqual(bars[0].source, "alpaca_sip_5Min")
            self.assertEqual(bars[1].close, 101)
            self.assertEqual(result.output_format, "csv")

        first_query = parse.parse_qs(parse.urlparse(str(transport.calls[0]["url"])).query)
        second_query = parse.parse_qs(parse.urlparse(str(transport.calls[1]["url"])).query)
        self.assertEqual(first_query["timeframe"], ["5Min"])
        self.assertEqual(first_query["feed"], ["sip"])
        self.assertEqual(second_query["page_token"], ["next-page"])
        self.assertEqual(transport.calls[0]["headers"]["APCA-API-KEY-ID"], "key")

    def test_config_loads_credentials_and_output_path_from_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AlpacaBarDownloadConfig.from_mapping(
                {
                    "market_data": {
                        "provider": "alpaca_sip",
                        "symbols": ["spy"],
                        "timeframe": "15min",
                        "start": "2024-01-02T14:30:00Z",
                        "end": "2024-01-02T21:00:00Z",
                        "base_url_env": "ALPACA_DATA_BASE_URL",
                    },
                    "credentials": {
                        "api_key_id_env": "ALPACA_API_KEY_ID",
                        "secret_key_env": "ALPACA_SECRET_KEY",
                    },
                    "output": {"path": str(Path(tmp) / "out.parquet"), "format": "parquet"},
                },
                env_values={
                    "ALPACA_API_KEY_ID": "key",
                    "ALPACA_SECRET_KEY": "secret",
                    "ALPACA_DATA_BASE_URL": "https://data.alpaca.test/v2",
                },
            )

        self.assertEqual(config.symbols, ["SPY"])
        self.assertEqual(config.timeframe, "15Min")
        self.assertEqual(config.feed, "sip")
        self.assertEqual(config.output_format, "parquet")
        self.assertEqual(config.api_key_id, "key")
        self.assertEqual(config.base_url, "https://data.alpaca.test/v2")

    def test_config_generates_output_path_from_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = AlpacaBarDownloadConfig.from_mapping(
                {
                    "market_data": {
                        "provider": "alpaca_sip",
                        "symbols": ["spy", "qqq"],
                        "timeframe": "15min",
                        "start": "2024-01-02T14:30:00Z",
                        "end": "2024-01-02T21:00:00Z",
                    },
                    "output": {
                        "directory": str(Path(tmp) / "downloads"),
                        "filename_template": (
                            "alpaca_{feed}_{symbols}_{timeframe}_{start}_{end}.{format}"
                        ),
                        "format": "parquet",
                    },
                },
                env_values={"ALPACA_API_KEY_ID": "key", "ALPACA_SECRET_KEY": "secret"},
            )

        self.assertEqual(config.output_format, "parquet")
        self.assertEqual(
            config.output_path.name,
            "alpaca_sip_spy-qqq_15min_20240102t143000z_20240102t210000z.parquet",
        )

    def test_config_infers_output_format_from_fixed_path_extension(self) -> None:
        config = AlpacaBarDownloadConfig.from_mapping(
            {
                "market_data": {
                    "provider": "alpaca_sip",
                    "symbols": ["SPY"],
                    "timeframe": "1min",
                    "start": "2024-01-02T14:30:00Z",
                    "end": "2024-01-02T21:00:00Z",
                },
                "output": {"path": "data/alpaca/bars.parquet"},
            },
            env_values={"ALPACA_API_KEY_ID": "key", "ALPACA_SECRET_KEY": "secret"},
        )

        self.assertEqual(config.output_format, "parquet")

    def test_rejects_unsupported_output_format(self) -> None:
        with self.assertRaises(ConfigurationError):
            AlpacaBarDownloadConfig.from_mapping(
                {
                    "market_data": {
                        "provider": "alpaca_sip",
                        "symbols": ["SPY"],
                        "timeframe": "1min",
                        "start": "2024-01-02T14:30:00Z",
                        "end": "2024-01-02T21:00:00Z",
                    },
                    "output": {"path": "bars.json", "format": "json"},
                },
                env_values={"ALPACA_API_KEY_ID": "key", "ALPACA_SECRET_KEY": "secret"},
            )

    def test_rejects_output_path_extension_mismatch(self) -> None:
        with self.assertRaises(ConfigurationError):
            AlpacaBarDownloadConfig.from_mapping(
                {
                    "market_data": {
                        "provider": "alpaca_sip",
                        "symbols": ["SPY"],
                        "timeframe": "1min",
                        "start": "2024-01-02T14:30:00Z",
                        "end": "2024-01-02T21:00:00Z",
                    },
                    "output": {"path": "data/alpaca/bars.csv", "format": "parquet"},
                },
                env_values={"ALPACA_API_KEY_ID": "key", "ALPACA_SECRET_KEY": "secret"},
            )

    @unittest.skipUnless(parquet_write_read_available(), "Parquet writer engine is not installed")
    def test_downloads_alpaca_bars_to_parquet_compatible_with_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "bars.parquet"
            config = AlpacaBarDownloadConfig(
                symbols=["SPY"],
                start="2024-01-02T14:30:00Z",
                end="2024-01-02T14:30:00Z",
                timeframe="1Min",
                feed="sip",
                output_path=output_path,
                output_format="parquet",
                api_key_id="key",
                secret_key="secret",
                base_url="https://data.alpaca.test/v2",
            )
            transport = FakeTransport(
                [
                    {
                        "bars": {
                            "SPY": [
                                {
                                    "t": "2024-01-02T14:30:00Z",
                                    "o": 100,
                                    "h": 101,
                                    "l": 99,
                                    "c": 100.5,
                                    "v": 1000,
                                    "n": 12,
                                    "vw": 100.2,
                                }
                            ]
                        }
                    }
                ]
            )
            client = AlpacaMarketDataClient(
                base_url=config.base_url,
                api_key_id="key",
                secret_key="secret",
                transport=transport,
            )

            result = download_alpaca_bars(config, client=client)

            self.assertEqual(result.output_format, "parquet")
            provider = LocalParquetProvider(output_path)
            bars = provider.get_history(
                ["SPY"],
                "2024-01-02T14:30:00Z",
                "2024-01-02T14:30:00Z",
                "MINUTE",
            )
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0].source, "alpaca_sip_1Min")
            self.assertEqual(bars[0].close, 100.5)


if __name__ == "__main__":
    unittest.main()
