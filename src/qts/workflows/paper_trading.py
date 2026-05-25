"""Paper trading workflow helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qts.core import load_runtime_config
from qts.engines import PaperTradingEngine


@dataclass(frozen=True)
class PaperTradingWorkflowResult:
    """Result of initializing or running the paper trading workflow."""

    engine: PaperTradingEngine
    status: dict[str, object]


def run_paper_trading_workflow(
    config_path: str | Path = "configs/paper_alpaca.yaml",
    *,
    mock: bool = False,
    max_events: int = 0,
    stop_after_run: bool = False,
) -> PaperTradingWorkflowResult:
    """Load paper config, start the paper engine, and optionally stop it."""
    overrides = {"broker": {"safety": {"mock_mode": True}}} if mock else None
    config = load_runtime_config(config_path, overrides=overrides)
    engine = PaperTradingEngine(config)
    status = engine.start(max_events=max_events)
    if stop_after_run:
        engine.stop("paper_runner_complete")
    return PaperTradingWorkflowResult(engine=engine, status=status)


__all__ = ["PaperTradingWorkflowResult", "run_paper_trading_workflow"]
