#!/usr/bin/env python3
"""Initialize a configured paper trading runtime."""

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
        help="use an in-memory paper broker client and do not require credentials",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="initialize, reconcile, print health, and exit",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="maximum market events to process before returning; 0 initializes only",
    )
    args = parser.parse_args(argv)

    overrides = {}
    if args.mock:
        overrides = {"broker": {"safety": {"mock_mode": True}}}

    try:
        config = load_runtime_config(args.config, overrides=overrides or None)
        engine = PaperTradingEngine(config)
        status = engine.start(max_events=args.max_events)
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
    event_loop = status.get("event_loop")
    if isinstance(event_loop, dict):
        print(
            "event loop: "
            f"processed={event_loop.get('processed_count', 0)} "
            f"skipped={event_loop.get('skipped_count', 0)} "
            f"duplicates={event_loop.get('duplicate_count', 0)}"
        )
    if args.dry_run or args.max_events > 0:
        engine.stop("paper_runner_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
