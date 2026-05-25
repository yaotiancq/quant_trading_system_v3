"""Backtest workflow helpers."""

from __future__ import annotations

from pathlib import Path

from qts.core import load_runtime_config
from qts.domain import BacktestResult
from qts.engines import BacktestEngine


def run_backtest_workflow(
    config_path: str | Path = "configs/backtest_fixture.yaml",
    *,
    output_dir: str | None = None,
    env_path: str | Path = ".env",
) -> BacktestResult:
    """Load a runtime config and run a deterministic local backtest."""
    overrides = {"reporting": {"output_dir": output_dir}} if output_dir else None
    config = load_runtime_config(Path(config_path), env_path=env_path, overrides=overrides)
    return BacktestEngine(config).run()


__all__ = ["run_backtest_workflow"]
