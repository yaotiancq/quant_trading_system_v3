from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from qts.core import StrategyError
from qts.domain import Bar, BarTimeframe, FeatureRecord, SignalDirection, StrategyConfig
from qts.features import FeaturePipeline, FeatureSpec
from qts.ml import DirectionalModel, FileModelRegistry
from qts.strategies import MLSignalStrategy, create_strategy


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_model() -> DirectionalModel:
    return DirectionalModel(
        model_id="strategy-model",
        feature_names=["ret_1"],
        feature_schema_version="ml_features_v1",
        weights={"ret_1": 100.0},
        feature_means={"ret_1": 0.0},
        decision_threshold=0.55,
        metadata={"horizon": "next_1_bars"},
    )


def make_bar(minutes: int = 0) -> Bar:
    return Bar(
        symbol="SPY",
        timestamp=NOW + timedelta(minutes=minutes),
        timeframe=BarTimeframe.MINUTE,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1000,
    )


class MLSignalStrategyTests(unittest.TestCase):
    def test_ml_strategy_converts_prediction_to_buy_and_sell_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            FileModelRegistry(tmp).save_model(make_model())
            strategy = MLSignalStrategy()
            strategy.initialize(
                StrategyConfig(
                    strategy_id="ml_test",
                    strategy_type="ml_directional",
                    symbols=["SPY"],
                    parameters={"model_id": "strategy-model", "registry_dir": tmp},
                ),
                data_portal=None,
            )

            buy = strategy.on_data(
                make_bar(0),
                FeatureRecord(
                    symbol="SPY",
                    timestamp=NOW,
                    values={"ret_1": 0.02},
                    schema_version="ml_features_v1",
                ),
            )
            sell = strategy.on_data(
                make_bar(1),
                FeatureRecord(
                    symbol="SPY",
                    timestamp=NOW + timedelta(minutes=1),
                    values={"ret_1": -0.02},
                    schema_version="ml_features_v1",
                ),
            )

        self.assertEqual(buy[0].direction, SignalDirection.BUY)
        self.assertEqual(sell[0].direction, SignalDirection.SELL)
        self.assertEqual(buy[0].reason, "ml_directional_prediction")
        self.assertIn("prediction", buy[0].metadata)

    def test_initialize_rejects_runtime_feature_schema_mismatch(self) -> None:
        class Portal:
            feature_pipeline = FeaturePipeline(
                [FeatureSpec("sma", {"window": 3})],
                schema_version="features_v1",
            )

        with tempfile.TemporaryDirectory() as tmp:
            FileModelRegistry(tmp).save_model(make_model())
            strategy = MLSignalStrategy()

            with self.assertRaises(StrategyError):
                strategy.initialize(
                    StrategyConfig(
                        strategy_id="ml_test",
                        strategy_type="ml_directional",
                        symbols=["SPY"],
                        parameters={"model_id": "strategy-model", "registry_dir": tmp},
                    ),
                    data_portal=Portal(),
                )

    def test_strategy_factory_supports_ml_directional_strategy(self) -> None:
        strategy = create_strategy(
            StrategyConfig(
                strategy_id="ml_test",
                strategy_type="ml_directional",
                symbols=["SPY"],
                parameters={"model_id": "placeholder"},
            )
        )

        self.assertIsInstance(strategy, MLSignalStrategy)


if __name__ == "__main__":
    unittest.main()
