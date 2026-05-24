"""Backtest report generation and artifact export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from qts.domain import BacktestResult, PortfolioSnapshot, TradeLedgerEntry

from .metrics import calculate_metrics, equity_curve


class BacktestReporter:
    """Generate metrics and lightweight report artifacts."""

    def generate_metrics(
        self,
        portfolio_snapshots: list[PortfolioSnapshot],
        trades: list[TradeLedgerEntry],
        config: Any | None = None,
    ) -> dict[str, Any]:
        reporting = getattr(config, "reporting", {}) or {}
        return dict(
            calculate_metrics(
                portfolio_snapshots,
                trades,
                annualization_factor=_optional_float(reporting.get("annualization_factor")),
                risk_free_rate=float(reporting.get("risk_free_rate", 0.0)),
            )
        )

    def generate_plots(self, backtest_result: BacktestResult, output_path: str | Path) -> list[Path]:
        return []

    def export_report(
        self,
        backtest_result: BacktestResult,
        output_path: str | Path,
        format: str = "markdown",
    ) -> dict[str, str]:
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = backtest_result.run_id
        metrics_path = output_dir / f"{run_id}_metrics.json"
        config_path = output_dir / f"{run_id}_config.json"
        trades_path = output_dir / f"{run_id}_trades.csv"
        cash_path = output_dir / f"{run_id}_cash.csv"
        equity_path = output_dir / f"{run_id}_equity_curve.csv"
        summary_path = output_dir / f"{run_id}_summary.md"

        metrics_path.write_text(
            json.dumps(backtest_result.metrics, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        config_path.write_text(
            json.dumps(backtest_result.config.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _write_csv(trades_path, [entry.to_dict() for entry in backtest_result.trade_ledger])
        _write_csv(cash_path, [entry.to_dict() for entry in backtest_result.cash_ledger])
        _write_csv(equity_path, equity_curve(backtest_result.portfolio_snapshots))
        summary_path.write_text(self.summarize(backtest_result), encoding="utf-8")

        return {
            "metrics": str(metrics_path),
            "config": str(config_path),
            "trades": str(trades_path),
            "cash": str(cash_path),
            "equity_curve": str(equity_path),
            "summary": str(summary_path),
        }

    def summarize(self, result: BacktestResult) -> str:
        metrics = result.metrics
        lines = [
            f"# Backtest Report: {result.run_id}",
            "",
            "## Summary",
            "",
            f"- Symbols: {', '.join(result.symbols)}",
            f"- Start: {result.start_time.isoformat()}",
            f"- End: {result.end_time.isoformat()}",
            f"- Total Return: {_format_percent(metrics.get('total_return'))}",
            f"- Max Drawdown: {_format_percent(metrics.get('max_drawdown'))}",
            f"- Sharpe Ratio: {_format_number(metrics.get('sharpe_ratio'))}",
            f"- Trades: {metrics.get('number_of_trades', 0)}",
            f"- Closed Trades: {metrics.get('number_of_closed_trades', 0)}",
            f"- Win Rate: {_format_percent(metrics.get('win_rate'))}",
            f"- Profit Factor: {_format_number(metrics.get('profit_factor'))}",
            "",
            "## Artifacts",
            "",
            "Metrics, trades, cash ledger, equity curve, and config summary are exported next to this report.",
        ]
        return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _format_percent(value: Any) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def _format_number(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


__all__ = ["BacktestReporter"]
