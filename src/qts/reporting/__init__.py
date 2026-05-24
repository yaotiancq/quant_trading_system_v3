"""Backtest reporting and metrics."""

from __future__ import annotations

from .charts import generate_backtest_charts, render_drawdown_svg, render_equity_curve_svg
from .metrics import calculate_metrics, equity_curve
from .reporter import BacktestReporter

__all__ = [
    "BacktestReporter",
    "calculate_metrics",
    "equity_curve",
    "generate_backtest_charts",
    "render_drawdown_svg",
    "render_equity_curve_svg",
]
