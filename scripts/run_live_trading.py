#!/usr/bin/env python3
"""Initialize the guarded live engine scaffold."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts.core import ConfigurationError, LiveSafetyError, ReconciliationError
from qts.workflows import run_live_trading_workflow


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
        help="explicitly enable live safety gates for dry-run initialization",
    )
    args = parser.parse_args(argv)

    try:
        result = run_live_trading_workflow(
            args.config,
            dry_run=args.dry_run,
            confirm_live_safety=args.confirm_live_safety,
        )
    except (ConfigurationError, LiveSafetyError, ReconciliationError, ValueError) as exc:
        print(f"live engine initialization failed: {exc}")
        return 2

    config = result.config
    health = result.health
    print(
        "live engine initialized: "
        f"run_id={config.run_id} status={health['status']} "
        f"dry_run={health.get('dry_run')} healthy={health['healthy']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
