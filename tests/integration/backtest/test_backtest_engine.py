from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qts.core import ConfigurationError, load_runtime_config
from qts.engines import BacktestEngine
from qts.strategies import create_strategy


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs" / "backtest_fixture.yaml"


def load_config(output_dir: str, strategy_parameters: dict[str, int] | None = None):
    overrides = {"reporting": {"output_dir": output_dir}}
    if strategy_parameters is not None:
        overrides["strategies"] = [
            {
                "strategy_id": "sma_cross_v1",
                "strategy_type": "sma_crossover",
                "symbols": ["SPY"],
                "enabled": True,
                "parameters": strategy_parameters,
            }
        ]
    return load_runtime_config(CONFIG, env_path=None, overrides=overrides)


class BacktestEngineIntegrationTests(unittest.TestCase):
    def test_backtest_engine_runs_sma_fixture_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = BacktestEngine(load_config(tmp)).run()

            self.assertEqual(len(result.fills), 2)
            self.assertEqual(len(result.trade_ledger), 2)
            self.assertAlmostEqual(result.metrics["total_return"], -0.0006)
            self.assertTrue(Path(result.artifacts["summary"]).is_file())
            self.assertTrue(Path(result.artifacts["trades"]).is_file())
            self.assertTrue(Path(result.artifacts["equity_curve"]).is_file())

    def test_backtest_engine_handles_empty_signal_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = BacktestEngine(
                load_config(tmp, {"fast_window": 20, "slow_window": 50})
            ).run()

            self.assertEqual(result.fills, [])
            self.assertEqual(result.trade_ledger, [])
            self.assertEqual(result.metrics["total_return"], 0.0)

    def test_backtest_data_portal_is_replay_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = BacktestEngine(load_config(tmp))
            engine.initialize()
            assert engine.data_portal is not None
            assert engine.provider is not None

            self.assertEqual(engine.data_portal.get_bars("SPY"), [])
            first_bar = next(
                engine.provider.iter_replay(
                    ["SPY"],
                    engine.config.start,
                    engine.config.end,
                    engine.config.timeframe,
                )
            )

            engine.step(first_bar)

            self.assertEqual(engine.data_portal.get_bars("SPY"), [first_bar])

    def test_backtest_engine_is_reproducible_for_fixed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            first = BacktestEngine(load_config(left)).run()
            second = BacktestEngine(load_config(right)).run()

        self.assertEqual([fill.to_dict() for fill in first.fills], [fill.to_dict() for fill in second.fills])
        self.assertEqual(
            [entry.to_dict() for entry in first.trade_ledger],
            [entry.to_dict() for entry in second.trade_ledger],
        )
        self.assertEqual(first.metrics, second.metrics)

    def test_backtest_engine_rejects_too_few_injected_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = BacktestEngine(load_config(tmp), strategies=[])

            with self.assertRaisesRegex(ConfigurationError, "injected strategy count"):
                engine.initialize()

    def test_backtest_engine_rejects_too_many_injected_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(tmp)
            strategies = [
                create_strategy(config.strategies[0]),
                create_strategy(config.strategies[0]),
            ]
            engine = BacktestEngine(config, strategies=strategies)

            with self.assertRaisesRegex(ConfigurationError, "injected strategy count"):
                engine.initialize()


if __name__ == "__main__":
    unittest.main()
