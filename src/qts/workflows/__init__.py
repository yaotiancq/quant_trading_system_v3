"""Reusable package-level command workflows."""

from __future__ import annotations

from .backtest import run_backtest_workflow
from .download_data import download_data_workflow
from .live_trading import LiveTradingWorkflowResult, live_dry_run_overrides, run_live_trading_workflow
from .paper_trading import PaperTradingWorkflowResult, run_paper_trading_workflow
from .reporting import generate_report_workflow
from .training import provider_from_config, train_from_mapping, train_model_workflow

__all__ = [
    "LiveTradingWorkflowResult",
    "PaperTradingWorkflowResult",
    "download_data_workflow",
    "generate_report_workflow",
    "live_dry_run_overrides",
    "provider_from_config",
    "run_backtest_workflow",
    "run_live_trading_workflow",
    "run_paper_trading_workflow",
    "train_from_mapping",
    "train_model_workflow",
]
