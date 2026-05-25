"""Reporting workflow helpers."""

from __future__ import annotations

from pathlib import Path

from qts.core import load_runtime_config
from qts.domain import BacktestResult
from qts.engines import BacktestEngine


def generate_report_workflow(
    config_path: str | Path = "configs/backtest_fixture.yaml",
    *,
    output_dir: str = "artifacts/reports",
    env_path: str | Path = ".env",
    generate_plots: bool = False,
) -> BacktestResult:
    """Run a backtest and write configured report artifacts."""
    reporting_overrides: dict[str, object] = {"output_dir": output_dir}
    if generate_plots:
        reporting_overrides["generate_plots"] = True
    config = load_runtime_config(
        Path(config_path),
        env_path=env_path,
        overrides={"reporting": reporting_overrides},
    )
    return BacktestEngine(config).run()


__all__ = ["generate_report_workflow"]
