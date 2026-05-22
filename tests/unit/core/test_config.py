from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qts.core import ConfigurationError, load_env_file, load_runtime_config, parse_yaml_mapping
from qts.domain import BarTimeframe, RuntimeMode


ROOT = Path(__file__).resolve().parents[3]


class ConfigTests(unittest.TestCase):
    def test_load_backtest_config_merges_base_and_mode_specific_files(self) -> None:
        config = load_runtime_config(ROOT / "configs" / "backtest.yaml", env_path=None)

        self.assertEqual(config.runtime_mode, RuntimeMode.BACKTEST)
        self.assertEqual(config.timeframe, BarTimeframe.MINUTE)
        self.assertEqual(config.symbols, ["SPY"])
        self.assertEqual(config.broker.broker_type, "backtest")
        self.assertEqual(config.broker.fill_policy, "next_bar_open")
        self.assertEqual(config.metadata["timezone"], "UTC")
        self.assertEqual(config.strategies[0].strategy_id, "sma_cross_v1")

    def test_invalid_config_raises_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                """
runtime:
  mode: BACKTEST
symbols: []
timeframe: MINUTE
market_data:
  provider: local_parquet
broker:
  broker_type: backtest
strategies: []
risk:
  sizing_method: fixed_notional
portfolio:
  starting_cash: 100000
execution:
  allow_fractional: false
""",
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_runtime_config(path, env_path=None)

    def test_env_file_loader_reads_key_value_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                """
# comment
export ALPACA_API_KEY_ID="abc"
ALPACA_SECRET_KEY='def'
""",
                encoding="utf-8",
            )

            values = load_env_file(env_path)

        self.assertEqual(values["ALPACA_API_KEY_ID"], "abc")
        self.assertEqual(values["ALPACA_SECRET_KEY"], "def")

    def test_simple_yaml_parser_handles_nested_list_mappings(self) -> None:
        data = parse_yaml_mapping(
            """
symbols: [SPY]
strategies:
  - strategy_id: s1
    strategy_type: demo
    symbols: [SPY]
    enabled: true
    parameters:
      window: 20
"""
        )

        self.assertEqual(data["symbols"], ["SPY"])
        self.assertEqual(data["strategies"][0]["parameters"]["window"], 20)


if __name__ == "__main__":
    unittest.main()
