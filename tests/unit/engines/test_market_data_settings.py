from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from qts.core import ConfigurationError
from qts.domain import (
    BarTimeframe,
    BrokerConfig,
    RiskConfig,
    RuntimeConfig,
    RuntimeMode,
    StrategyConfig,
)
from qts.engines.backtest_engine import _provider_from_config as backtest_provider_from_config
from qts.engines.market_data import resolve_event_market_data_provider
from scripts.train_model import _provider_from_config as training_provider_from_config


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_config(
    provider: str,
    *,
    timeframe: BarTimeframe = BarTimeframe.MINUTE,
    market_data_overrides: dict[str, object] | None = None,
) -> RuntimeConfig:
    market_data = {"provider": provider}
    market_data.update(market_data_overrides or {})
    return RuntimeConfig(
        run_id="engine-provider-test",
        runtime_mode=RuntimeMode.PAPER,
        symbols=["SPY"],
        start=NOW,
        end=NOW,
        timeframe=timeframe,
        market_data=market_data,
        broker=BrokerConfig(broker_type="alpaca_paper", paper=True),
        strategies=[
            StrategyConfig(
                strategy_id="sma",
                strategy_type="sma_crossover",
                symbols=["SPY"],
            )
        ],
        risk=RiskConfig(sizing_method="fixed_quantity", sizing_parameters={"quantity": 1}),
        portfolio={"starting_cash": 100000, "currency": "USD"},
        execution={"allow_fractional": False},
    )


class EngineMarketDataSettingsTests(unittest.TestCase):
    def test_event_market_data_provider_is_selected_from_config(self) -> None:
        provider = resolve_event_market_data_provider(
            make_config("external_events"),
            engine_name="PaperTradingEngine",
        )

        self.assertEqual(provider, "external_events")

    def test_unsupported_event_market_data_provider_raises(self) -> None:
        with self.assertRaises(ConfigurationError):
            resolve_event_market_data_provider(
                make_config("alpaca"),
                engine_name="PaperTradingEngine",
            )

    def test_backtest_local_csv_provider_uses_configured_default_timeframe(self) -> None:
        with TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bars.csv"
            csv_path.write_text(
                "symbol,timestamp,open,high,low,close,volume\n"
                "SPY,2026-01-05T14:30:00Z,100,101,99,100.5,1000\n",
                encoding="utf-8",
            )
            config = make_config(
                "local_csv",
                timeframe=BarTimeframe.HOUR,
                market_data_overrides={"path": str(csv_path)},
            )

            provider = backtest_provider_from_config(config)
            bars = provider.get_history(["SPY"], NOW, NOW, BarTimeframe.HOUR)

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].timeframe, BarTimeframe.HOUR)

    def test_training_local_csv_provider_uses_configured_default_timeframe(self) -> None:
        with TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bars.csv"
            csv_path.write_text(
                "symbol,timestamp,open,high,low,close,volume\n"
                "SPY,2026-01-05T14:30:00Z,100,101,99,100.5,1000\n",
                encoding="utf-8",
            )

            provider = training_provider_from_config(
                {
                    "provider": "local_csv",
                    "path": str(csv_path),
                    "timeframe": "HOUR",
                }
            )
            bars = provider.get_history(["SPY"], NOW, NOW, BarTimeframe.HOUR)

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].timeframe, BarTimeframe.HOUR)

    def test_backtest_local_parquet_provider_uses_configured_default_timeframe(self) -> None:
        config = make_config(
            "local_parquet",
            timeframe=BarTimeframe.HOUR,
            market_data_overrides={"path": "data/hourly.parquet"},
        )

        with patch(
            "qts.market_data.providers._read_parquet_rows",
            return_value=[
                {
                    "symbol": "SPY",
                    "timestamp": "2026-01-05T14:30:00Z",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100.5,
                    "volume": 1000,
                }
            ],
        ):
            provider = backtest_provider_from_config(config)
            bars = provider.get_history(["SPY"], NOW, NOW, BarTimeframe.HOUR)

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].timeframe, BarTimeframe.HOUR)

    def test_training_local_parquet_provider_uses_configured_default_timeframe(self) -> None:
        with patch(
            "qts.market_data.providers._read_parquet_rows",
            return_value=[
                {
                    "symbol": "SPY",
                    "timestamp": "2026-01-05T14:30:00Z",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100.5,
                    "volume": 1000,
                }
            ],
        ):
            provider = training_provider_from_config(
                {
                    "provider": "local_parquet",
                    "path": "data/hourly.parquet",
                    "timeframe": "HOUR",
                }
            )
            bars = provider.get_history(["SPY"], NOW, NOW, BarTimeframe.HOUR)

        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].timeframe, BarTimeframe.HOUR)


if __name__ == "__main__":
    unittest.main()
