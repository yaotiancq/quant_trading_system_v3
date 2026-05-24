from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qts.core import load_runtime_config
from qts.domain import (
    BacktestResult,
    Fill,
    OrderSide,
    PortfolioSnapshot,
    TradeLedgerEntry,
)
from qts.reporting import BacktestReporter, calculate_metrics, render_drawdown_svg, render_equity_curve_svg


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]


def snapshot(minutes: int, equity: float, gross: float = 0.0) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=NOW + timedelta(minutes=minutes),
        cash=equity - gross,
        equity=equity,
        positions_value=gross,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        gross_exposure=gross,
        net_exposure=gross,
    )


def trade(entry_id: str, pnl: float) -> TradeLedgerEntry:
    return TradeLedgerEntry(
        entry_id=entry_id,
        fill_id=f"fill-{entry_id}",
        order_id=f"order-{entry_id}",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=NOW,
        side=OrderSide.SELL,
        quantity=1,
        price=100,
        commission=0,
        realized_pnl_delta=pnl,
        position_quantity_after=0,
        average_cost_after=0,
    )


class ReportingMetricTests(unittest.TestCase):
    def test_calculate_metrics_includes_return_drawdown_and_trade_stats(self) -> None:
        snapshots = [
            snapshot(0, 100),
            snapshot(1, 110),
            snapshot(2, 105),
            snapshot(3, 120),
        ]
        metrics = calculate_metrics(snapshots, [trade("1", 10), trade("2", -5)])

        self.assertAlmostEqual(metrics["total_return"], 0.2)
        self.assertAlmostEqual(metrics["max_drawdown"], 5 / 110)
        self.assertEqual(metrics["win_rate"], 0.5)
        self.assertEqual(metrics["profit_factor"], 2.0)
        self.assertEqual(metrics["number_of_trades"], 2)

    def test_calculate_metrics_uses_reporting_annualization_settings(self) -> None:
        snapshots = [
            snapshot(0, 100),
            snapshot(1, 102),
            snapshot(2, 101),
        ]

        default_metrics = calculate_metrics(snapshots, [])
        configured_metrics = calculate_metrics(
            snapshots,
            [],
            annualization_factor=252,
            risk_free_rate=0.05,
        )

        self.assertIsNone(default_metrics["annualized_return"])
        self.assertIsNotNone(configured_metrics["annualized_return"])
        self.assertIsNotNone(configured_metrics["sharpe_ratio"])
        self.assertNotEqual(default_metrics["sharpe_ratio"], configured_metrics["sharpe_ratio"])

    def test_reporter_passes_configured_reporting_metrics_settings(self) -> None:
        config = load_runtime_config(
            ROOT / "configs" / "backtest_fixture.yaml",
            env_path=None,
            overrides={"reporting": {"annualization_factor": 252, "risk_free_rate": 0.05}},
        )
        snapshots = [
            snapshot(0, 100),
            snapshot(1, 102),
            snapshot(2, 101),
        ]

        metrics = BacktestReporter().generate_metrics(snapshots, [], config)

        self.assertIsNotNone(metrics["annualized_return"])

    def test_reporter_exports_metrics_ledgers_equity_curve_and_summary(self) -> None:
        config = load_runtime_config(ROOT / "configs" / "backtest_fixture.yaml", env_path=None)
        snapshots = [snapshot(0, 100000), snapshot(1, 100100, gross=1000)]
        metrics = calculate_metrics(snapshots, [trade("1", 10)])
        result = BacktestResult(
            run_id="report-test",
            config=config,
            start_time=snapshots[0].timestamp,
            end_time=snapshots[-1].timestamp,
            symbols=["SPY"],
            portfolio_snapshots=snapshots,
            orders=[],
            fills=[],
            trade_ledger=[trade("1", 10)],
            cash_ledger=[],
            metrics=metrics,
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = BacktestReporter().export_report(result, tmp)
            self.assertTrue(Path(artifacts["summary"]).is_file())
            self.assertTrue(Path(artifacts["equity_curve"]).is_file())
            exported_metrics = json.loads(Path(artifacts["metrics"]).read_text(encoding="utf-8"))

        self.assertEqual(exported_metrics["number_of_trades"], 1)

    def test_reporter_generates_static_svg_charts_when_enabled(self) -> None:
        config = load_runtime_config(
            ROOT / "configs" / "backtest_fixture.yaml",
            env_path=None,
            overrides={"reporting": {"generate_plots": True}},
        )
        snapshots = [snapshot(0, 100000), snapshot(1, 100100, gross=1000), snapshot(2, 99900)]
        result = BacktestResult(
            run_id="chart-test",
            config=config,
            start_time=snapshots[0].timestamp,
            end_time=snapshots[-1].timestamp,
            symbols=["SPY"],
            portfolio_snapshots=snapshots,
            orders=[],
            fills=[
                Fill(
                    fill_id="fill-chart-1",
                    order_id="order-chart-1",
                    symbol="SPY",
                    timestamp=snapshots[1].timestamp,
                    side=OrderSide.BUY,
                    quantity=1,
                    price=100,
                    commission=0,
                    source="test",
                )
            ],
            trade_ledger=[],
            cash_ledger=[],
            metrics=calculate_metrics(snapshots, []),
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = BacktestReporter().export_report(result, tmp)
            equity_chart = Path(artifacts["equity_curve_chart"])
            drawdown_chart = Path(artifacts["drawdown_chart"])
            equity_text = equity_chart.read_text(encoding="utf-8")
            drawdown_text = drawdown_chart.read_text(encoding="utf-8")
            summary = Path(artifacts["summary"]).read_text(encoding="utf-8")

        self.assertIn("<svg", equity_text)
        self.assertIn("Equity Curve - chart-test", equity_text)
        self.assertIn("BUY 1 SPY", equity_text)
        self.assertIn("<svg", drawdown_text)
        self.assertIn("Static SVG equity and drawdown charts", summary)

    def test_chart_renderers_handle_empty_snapshots(self) -> None:
        config = load_runtime_config(ROOT / "configs" / "backtest_fixture.yaml", env_path=None)
        result = BacktestResult(
            run_id="empty-chart-test",
            config=config,
            start_time=NOW,
            end_time=NOW,
            symbols=["SPY"],
            portfolio_snapshots=[],
            orders=[],
            fills=[],
            trade_ledger=[],
            cash_ledger=[],
            metrics={},
        )

        self.assertIn("No portfolio snapshots", render_equity_curve_svg(result))
        self.assertIn("No portfolio snapshots", render_drawdown_svg(result))

    def test_plot_failure_preserves_non_plot_artifacts(self) -> None:
        class FailingPlotReporter(BacktestReporter):
            def generate_plots(
                self,
                backtest_result: BacktestResult,
                output_path: str | Path,
            ) -> list[Path]:
                raise RuntimeError("plot backend unavailable")

        config = load_runtime_config(
            ROOT / "configs" / "backtest_fixture.yaml",
            env_path=None,
            overrides={"reporting": {"generate_plots": True}},
        )
        snapshots = [snapshot(0, 100000), snapshot(1, 100100)]
        result = BacktestResult(
            run_id="plot-failure-test",
            config=config,
            start_time=snapshots[0].timestamp,
            end_time=snapshots[-1].timestamp,
            symbols=["SPY"],
            portfolio_snapshots=snapshots,
            orders=[],
            fills=[],
            trade_ledger=[],
            cash_ledger=[],
            metrics=calculate_metrics(snapshots, []),
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = FailingPlotReporter().export_report(result, tmp)
            summary = Path(artifacts["summary"]).read_text(encoding="utf-8")
            metrics_exists = Path(artifacts["metrics"]).is_file()

        self.assertNotIn("equity_curve_chart", artifacts)
        self.assertTrue(metrics_exists)
        self.assertIn("plot generation failed: plot backend unavailable", summary)


if __name__ == "__main__":
    unittest.main()
