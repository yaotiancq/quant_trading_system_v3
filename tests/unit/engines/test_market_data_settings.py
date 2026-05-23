from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.core import ConfigurationError
from qts.domain import (
    BarTimeframe,
    BrokerConfig,
    RiskConfig,
    RuntimeConfig,
    RuntimeMode,
    StrategyConfig,
)
from qts.engines.market_data import resolve_event_market_data_provider


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_config(provider: str) -> RuntimeConfig:
    return RuntimeConfig(
        run_id="engine-provider-test",
        runtime_mode=RuntimeMode.PAPER,
        symbols=["SPY"],
        start=NOW,
        end=NOW,
        timeframe=BarTimeframe.MINUTE,
        market_data={"provider": provider},
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


if __name__ == "__main__":
    unittest.main()
