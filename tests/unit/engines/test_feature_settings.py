from __future__ import annotations

import unittest

from qts.core import ConfigurationError
from qts.domain import StrategyConfig
from qts.engines.features import feature_pipeline_settings_from_strategies


class EngineFeatureSettingsTests(unittest.TestCase):
    def test_rule_strategy_specs_are_inferred(self) -> None:
        specs, schema_version = feature_pipeline_settings_from_strategies(
            [
                StrategyConfig(
                    strategy_id="sma",
                    strategy_type="sma_crossover",
                    symbols=["SPY"],
                    parameters={"fast_window": 5, "slow_window": 10},
                )
            ]
        )

        self.assertEqual(schema_version, "features_v1")
        self.assertEqual([spec.output_names for spec in specs], [["sma_5"], ["sma_10"]])

    def test_explicit_ml_feature_config_supplies_specs_and_schema(self) -> None:
        specs, schema_version = feature_pipeline_settings_from_strategies(
            [
                StrategyConfig(
                    strategy_id="ml",
                    strategy_type="ml_directional",
                    symbols=["SPY"],
                    feature_config={
                        "schema_version": "ml_features_v1",
                        "specs": [
                            {"name": "returns", "parameters": {"window": 1}},
                            {"name": "sma", "parameters": {"window": 3}},
                        ],
                    },
                )
            ]
        )

        self.assertEqual(schema_version, "ml_features_v1")
        self.assertEqual([spec.output_names for spec in specs], [["ret_1"], ["sma_3"]])

    def test_conflicting_schema_versions_raise(self) -> None:
        configs = [
            StrategyConfig(
                strategy_id="left",
                strategy_type="ml_directional",
                symbols=["SPY"],
                feature_config={"schema_version": "left_v1", "specs": []},
            ),
            StrategyConfig(
                strategy_id="right",
                strategy_type="ml_directional",
                symbols=["SPY"],
                feature_config={"schema_version": "right_v1", "specs": []},
            ),
        ]

        with self.assertRaises(ConfigurationError):
            feature_pipeline_settings_from_strategies(configs)


if __name__ == "__main__":
    unittest.main()
