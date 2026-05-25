from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qts.domain import RuntimeMode
from qts.workflows import (
    download_data_workflow,
    run_backtest_workflow,
    run_live_trading_workflow,
    run_paper_trading_workflow,
    train_model_workflow,
)


ROOT = Path(__file__).resolve().parents[3]


class WorkflowTests(unittest.TestCase):
    def test_backtest_workflow_returns_result_with_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_backtest_workflow(
                ROOT / "configs" / "backtest_fixture.yaml",
                output_dir=tmp,
            )

        self.assertEqual(result.run_id, "backtest-fixture-sma")
        self.assertIn("summary", result.artifacts)
        self.assertIn("total_return", result.metrics)

    def test_paper_workflow_initializes_fake_stream_with_mock_broker(self) -> None:
        result = run_paper_trading_workflow(
            ROOT / "configs" / "paper_fake_stream.yaml",
            max_events=1,
            stop_after_run=True,
        )

        self.assertEqual(result.engine.config.runtime_mode, RuntimeMode.PAPER)
        self.assertEqual(result.status["event_loop"]["processed_count"], 1)
        self.assertFalse(result.engine._running)

    def test_live_workflow_preserves_dry_run_safety_mode(self) -> None:
        result = run_live_trading_workflow(
            ROOT / "configs" / "live_alpaca.yaml",
            dry_run=True,
            confirm_live_safety=True,
        )

        self.assertEqual(result.config.runtime_mode, RuntimeMode.LIVE)
        self.assertTrue(result.health["dry_run"])
        self.assertEqual(result.health["live_order_submission_count"], 0)

    def test_download_workflow_builds_config_without_network_when_downloader_is_mocked(self) -> None:
        expected = SimpleNamespace(row_count=0)
        with patch("qts.workflows.download_data.download_alpaca_bars", return_value=expected) as mock:
            result = download_data_workflow(
                ROOT / "configs" / "data" / "alpaca_sip_bars.yaml",
                env_path=ROOT / ".env.example",
                symbols="spy, aapl",
                timeframe="5min",
                output_format="csv",
            )

        self.assertIs(result, expected)
        config = mock.call_args.args[0]
        self.assertEqual(config.symbols, ["SPY", "AAPL"])
        self.assertEqual(config.timeframe, "5Min")
        self.assertEqual(config.output_format, "csv")

    def test_training_workflow_runs_against_fixture_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = train_model_workflow(
                ROOT / "configs" / "ml" / "directional_baseline.yaml",
                output_dir=tmp,
            )
            self.assertEqual(result["model"].model_id, "directional_fixture_v1")
            self.assertTrue(result["artifact_path"].is_file())
            self.assertTrue(result["manifest_path"].is_file())


if __name__ == "__main__":
    unittest.main()
