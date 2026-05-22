#!/usr/bin/env python3
"""Initialize the Alpaca paper trading runtime."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts.core import BrokerError, ConfigurationError, load_runtime_config
from qts.engines import PaperTradingEngine


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/paper_alpaca.yaml",
        help="paper trading runtime config path",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="use an in-memory Alpaca client and do not require credentials",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="initialize, reconcile, print health, and exit",
    )
    args = parser.parse_args(argv)

    overrides = {}
    if args.mock:
        overrides = {"broker": {"safety": {"mock_mode": True}}}

    try:
        config = load_runtime_config(args.config, overrides=overrides or None)
        engine = PaperTradingEngine(config)
        status = engine.start(max_events=0)
    except (BrokerError, ConfigurationError) as exc:
        print(f"paper trading initialization failed: {exc}")
        return 2

    reconciliation = status.get("reconciliation") or {}
    print(
        f"paper engine {status['run_id']}: "
        f"healthy={status['healthy']} "
        f"mock_mode={status['mock_mode']} "
        f"reconciliation={reconciliation.get('status', 'unknown')}"
    )
    if args.dry_run:
        engine.stop("dry_run_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
