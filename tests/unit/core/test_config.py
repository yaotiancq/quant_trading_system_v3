from __future__ import annotations

import os
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
        self.assertEqual(config.market_data["provider"], "local_csv")
        self.assertEqual(config.market_data["path"], str(ROOT / "data" / "alpaca"))
        self.assertEqual(config.bar_interval, "1Min")
        self.assertEqual(config.metadata["timezone"], "UTC")
        self.assertEqual(config.strategies[0].strategy_id, "sma_cross_v1")
        self.assertEqual(config.strategies[0].parameters["slow_window"], 40)
        self.assertIn(str(ROOT / "configs" / "strategies" / "sma_crossover.yaml"), config.metadata["source_files"])

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

    def test_strategy_and_risk_refs_resolve_with_inline_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
            configs = root / "configs"
            (configs / "strategies").mkdir(parents=True)
            (configs / "risk").mkdir()
            (configs / "strategies" / "sma.yaml").write_text(
                """
strategy_id: shared_sma
strategy_type: sma_crossover
symbols: [SPY]
enabled: true
parameters:
  fast_window: 5
  slow_window: 10
""",
                encoding="utf-8",
            )
            (configs / "risk" / "base.yaml").write_text(
                """
sizing_method: fixed_notional
sizing_parameters:
  notional_per_trade: 1000
""",
                encoding="utf-8",
            )
            config_path = configs / "runtime.yaml"
            config_path.write_text(
                """
runtime:
  mode: BACKTEST
symbols: [SPY]
timeframe: MINUTE
date_range:
  start: 2024-01-02T14:30:00Z
  end: 2024-01-02T14:35:00Z
market_data:
  provider: local_csv
  path: data/bars.csv
broker:
  broker_type: backtest
strategies:
  - config_ref: strategies/sma.yaml
    parameters:
      slow_window: 20
risk_ref: risk/base.yaml
risk:
  sizing_parameters:
    notional_per_trade: 2500
portfolio:
  starting_cash: 100000
execution:
  allow_fractional: false
""",
                encoding="utf-8",
            )

            config = load_runtime_config(config_path, env_path=None)

        self.assertEqual(config.strategies[0].strategy_id, "shared_sma")
        self.assertEqual(config.strategies[0].parameters, {"fast_window": 5, "slow_window": 20})
        self.assertEqual(config.risk.sizing_parameters, {"notional_per_trade": 2500})

    def test_reflects_changes_to_referenced_strategy_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
            configs = root / "configs"
            (configs / "strategies").mkdir(parents=True)
            (configs / "risk").mkdir()
            strategy_path = configs / "strategies" / "sma.yaml"
            strategy_path.write_text(
                """
strategy_id: shared_sma
strategy_type: sma_crossover
symbols: [SPY]
enabled: true
parameters:
  fast_window: 5
  slow_window: 10
""",
                encoding="utf-8",
            )
            (configs / "risk" / "base.yaml").write_text(
                """
sizing_method: fixed_quantity
sizing_parameters:
  quantity: 1
""",
                encoding="utf-8",
            )
            config_path = configs / "runtime.yaml"
            config_path.write_text(
                """
runtime:
  mode: BACKTEST
symbols: [SPY]
timeframe: MINUTE
date_range:
  start: 2024-01-02T14:30:00Z
  end: 2024-01-02T14:35:00Z
market_data:
  provider: local_csv
  path: data/bars.csv
broker:
  broker_type: backtest
strategies:
  - config_ref: strategies/sma.yaml
risk_ref: risk/base.yaml
portfolio:
  starting_cash: 100000
execution:
  allow_fractional: false
""",
                encoding="utf-8",
            )
            first = load_runtime_config(config_path, env_path=None)
            strategy_path.write_text(
                strategy_path.read_text(encoding="utf-8").replace("slow_window: 10", "slow_window: 30"),
                encoding="utf-8",
            )
            second = load_runtime_config(config_path, env_path=None)

        self.assertEqual(first.strategies[0].parameters["slow_window"], 10)
        self.assertEqual(second.strategies[0].parameters["slow_window"], 30)

    def test_unknown_nested_config_field_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                """
runtime:
  mode: BACKTEST
symbols: [SPY]
timeframe: MINUTE
date_range:
  start: 2024-01-02T14:30:00Z
  end: 2024-01-02T14:35:00Z
market_data:
  provider: local_csv
  path: data/bars.csv
broker:
  broker_type: backtest
strategies:
  - strategy_id: sma
    strategy_type: sma_crossover
    symbols: [SPY]
    parameters:
      fast_window: 2
      slow_window: 3
risk:
  sizing_method: fixed_quantity
  sizing_parameters:
    quantity: 1
portfolio:
  starting_cash: 100000
execution:
  allow_fracional: false
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigurationError, "execution"):
                load_runtime_config(path, env_path=None)

    def test_invalid_sizing_parameters_fail_at_config_load_time(self) -> None:
        cases = [
            ("fixed_quantity", "quantity", 0),
            ("fixed_notional", "notional_per_trade", 0),
            ("percent_equity", "percent", 1.5),
        ]
        for method, key, value in cases:
            with self.subTest(method=method):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "bad.yaml"
                    path.write_text(
                        f"""
runtime:
  mode: BACKTEST
symbols: [SPY]
timeframe: MINUTE
date_range:
  start: 2024-01-02T14:30:00Z
  end: 2024-01-02T14:35:00Z
market_data:
  provider: local_csv
  path: data/bars.csv
broker:
  broker_type: backtest
strategies:
  - strategy_id: sma
    strategy_type: sma_crossover
    symbols: [SPY]
    parameters:
      fast_window: 2
      slow_window: 3
risk:
  sizing_method: {method}
  sizing_parameters:
    {key}: {value}
portfolio:
  starting_cash: 100000
execution:
  allow_fractional: false
""",
                        encoding="utf-8",
                    )

                    with self.assertRaises(ConfigurationError):
                        load_runtime_config(path, env_path=None)

    def test_absolute_config_path_resolves_local_paths_from_project_root(self) -> None:
        current = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                config = load_runtime_config(ROOT / "configs" / "backtest_fixture.yaml", env_path=None)
            finally:
                os.chdir(current)

        self.assertEqual(
            config.market_data["path"],
            str(ROOT / "tests" / "fixtures" / "market_data" / "backtest_sma_cross.csv"),
        )
        self.assertEqual(config.reporting["output_dir"], str(ROOT / "artifacts" / "reports"))

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
