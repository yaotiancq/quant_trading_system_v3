#!/usr/bin/env python3
"""Initialize the guarded Phase 8 live engine scaffold."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts.core import ConfigurationError, LiveSafetyError, ReconciliationError, load_runtime_config
from qts.engines import LiveEngine


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/live_alpaca.yaml",
        help="live runtime config path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use the dry-run live brokerage scaffold; no orders are submitted",
    )
    parser.add_argument(
        "--confirm-live-safety",
        action="store_true",
        help="explicitly enable Phase 8 live safety gates for dry-run initialization",
    )
    args = parser.parse_args(argv)

    try:
        base_config = load_runtime_config(args.config)
        overrides = _dry_run_overrides(base_config.symbols, args.confirm_live_safety) if args.dry_run else {}
        config = load_runtime_config(args.config, overrides=overrides)
        engine = LiveEngine(config)
        health = engine.start(max_events=0)
    except (ConfigurationError, LiveSafetyError, ReconciliationError, ValueError) as exc:
        print(f"live engine initialization failed: {exc}")
        return 2

    print(
        "live engine initialized: "
        f"run_id={config.run_id} status={health['status']} "
        f"dry_run={health.get('dry_run')} healthy={health['healthy']}"
    )
    engine.stop(reason="dry-run initialization complete")
    return 0


def _dry_run_overrides(symbols: list[str], confirm_live_safety: bool) -> dict[str, object]:
    safety = {
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


if __name__ == "__main__":
    raise SystemExit(main())
