from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.core import StrategyError
from qts.domain import Bar, BarTimeframe, FeatureRecord, SignalDirection, StrategyConfig
from qts.strategies import RSIMeanReversionStrategy, SMACrossoverStrategy, create_strategy


UTC = timezone.utc
BASE = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def make_bar(symbol: str = "SPY", minutes: int = 0, close: float = 100.0) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=BASE + timedelta(minutes=minutes),
        timeframe=BarTimeframe.MINUTE,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
    )


def make_features(bar: Bar, values: dict[str, float]) -> FeatureRecord:
    return FeatureRecord(
        symbol=bar.symbol,
        timestamp=bar.timestamp,
        values=values,
        schema_version="test_features_v1",
    )


class RuleBasedStrategyTests(unittest.TestCase):
    def test_sma_crossover_emits_buy_and_sell_signals_on_crosses(self) -> None:
        strategy = SMACrossoverStrategy(
            StrategyConfig(
                strategy_id="sma_test",
                strategy_type="sma_crossover",
                symbols=["SPY"],
                parameters={"fast_window": 2, "slow_window": 3},
            )
        )

        first = make_bar(minutes=0)
        second = make_bar(minutes=1)
        third = make_bar(minutes=2)

        self.assertEqual(
            strategy.on_data(first, make_features(first, {"sma_2": 100.0, "sma_3": 101.0})),
            [],
        )
        buy_signals = strategy.on_data(
            second,
            make_features(second, {"sma_2": 102.0, "sma_3": 101.0}),
        )
        sell_signals = strategy.on_data(
            third,
            make_features(third, {"sma_2": 100.0, "sma_3": 101.0}),
        )

        self.assertEqual(len(buy_signals), 1)
        self.assertEqual(buy_signals[0].direction, SignalDirection.BUY)
        self.assertEqual(buy_signals[0].reason, "fast_sma_crossed_above_slow_sma")
        self.assertEqual(len(sell_signals), 1)
        self.assertEqual(sell_signals[0].direction, SignalDirection.SELL)
        self.assertEqual(sell_signals[0].reason, "fast_sma_crossed_below_slow_sma")

    def test_rsi_mean_reversion_emits_threshold_cross_signals(self) -> None:
        strategy = RSIMeanReversionStrategy(
            StrategyConfig(
                strategy_id="rsi_test",
                strategy_type="rsi_mean_reversion",
                symbols=["SPY"],
                parameters={"window": 3, "oversold": 30, "overbought": 70},
            )
        )

        first = make_bar(minutes=0)
        second = make_bar(minutes=1)
        third = make_bar(minutes=2)

        self.assertEqual(strategy.on_data(first, make_features(first, {"rsi_3": 40.0})), [])
        buy_signals = strategy.on_data(second, make_features(second, {"rsi_3": 25.0}))
        sell_signals = strategy.on_data(third, make_features(third, {"rsi_3": 75.0}))

        self.assertEqual(len(buy_signals), 1)
        self.assertEqual(buy_signals[0].direction, SignalDirection.BUY)
        self.assertEqual(buy_signals[0].reason, "rsi_crossed_below_oversold")
        self.assertEqual(len(sell_signals), 1)
        self.assertEqual(sell_signals[0].direction, SignalDirection.SELL)
        self.assertEqual(sell_signals[0].reason, "rsi_crossed_above_overbought")

    def test_strategy_rejects_unsupported_symbol(self) -> None:
        strategy = SMACrossoverStrategy(
            StrategyConfig(
                strategy_id="sma_test",
                strategy_type="sma_crossover",
                symbols=["SPY"],
                parameters={"fast_window": 2, "slow_window": 3},
            )
        )
        bar = make_bar(symbol="QQQ")

        with self.assertRaises(StrategyError):
            strategy.on_data(bar, make_features(bar, {"sma_2": 102.0, "sma_3": 101.0}))

    def test_create_strategy_factory_supports_phase_three_examples(self) -> None:
        sma = create_strategy(
            StrategyConfig(
                strategy_id="sma_test",
                strategy_type="sma_crossover",
                symbols=["SPY"],
                parameters={"fast_window": 2, "slow_window": 3},
            )
        )
        rsi = create_strategy(
            StrategyConfig(
                strategy_id="rsi_test",
                strategy_type="rsi_mean_reversion",
                symbols=["SPY"],
                parameters={"window": 3},
            )
        )

        self.assertIsInstance(sma, SMACrossoverStrategy)
        self.assertIsInstance(rsi, RSIMeanReversionStrategy)


if __name__ == "__main__":
    unittest.main()
