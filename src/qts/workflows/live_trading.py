"""Live trading workflow helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qts.core import load_runtime_config
from qts.domain import RuntimeConfig
from qts.engines import LiveEngine


@dataclass(frozen=True)
class LiveTradingWorkflowResult:
    """Result of initializing the guarded live workflow."""

    config: RuntimeConfig
    engine: LiveEngine
    health: dict[str, object]


def run_live_trading_workflow(
    config_path: str | Path = "configs/live_alpaca.yaml",
    *,
    dry_run: bool = False,
    confirm_live_safety: bool = False,
    stop_after_start: bool = True,
) -> LiveTradingWorkflowResult:
    """Load live config, start the guarded live engine, and optionally stop it."""
    if dry_run:
        base_config = load_runtime_config(config_path)
        overrides = live_dry_run_overrides(base_config.symbols, confirm_live_safety)
        config = load_runtime_config(config_path, overrides=overrides)
    else:
        config = load_runtime_config(config_path)
    engine = LiveEngine(config)
    health = engine.start(max_events=0)
    if stop_after_start:
        engine.stop(reason="dry-run initialization complete")
    return LiveTradingWorkflowResult(config=config, engine=engine, health=health)


def live_dry_run_overrides(
    symbols: list[str],
    confirm_live_safety: bool,
) -> dict[str, object]:
    """Return script-compatible dry-run live safety overrides."""
    safety: dict[str, object] = {
        "dry_run": True,
        "mock_mode": True,
        "dry_run_account_id": "dry-run-live",
        "dry_run_cash": 100000,
    }
    if confirm_live_safety:
        safety.update(
            {
                "live_enabled": True,
                "confirm_live_trading": False,
                "allowed_account_ids": ["dry-run-live"],
                "allowed_symbols": list(symbols),
                "max_order_notional": 1000,
                "max_order_quantity": 10,
            }
        )
    return {
        "broker": {
            "account_id": "dry-run-live",
            "safety": safety,
        }
    }


__all__ = [
    "LiveTradingWorkflowResult",
    "live_dry_run_overrides",
    "run_live_trading_workflow",
]
