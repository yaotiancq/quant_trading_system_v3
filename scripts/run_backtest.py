#!/usr/bin/env python3
"""Run a deterministic local backtest."""

from __future__ import annotations

import argparse
from pathlib import Path

from qts.core import load_runtime_config
from qts.engines import BacktestEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/backtest_fixture.yaml",
        help="Runtime config path.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override report output directory.",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help="Optional .env path for config loading.",
    )
    args = parser.parse_args(argv)

    overrides = {"reporting": {"output_dir": args.output_dir}} if args.output_dir else None
    config = load_runtime_config(Path(args.config), env_path=args.env, overrides=overrides)
    result = BacktestEngine(config).run()
    print(
        f"backtest {result.run_id}: {len(result.fills)} fills, "
        f"total_return={result.metrics['total_return']:.6f}"
    )
    print(f"summary: {result.artifacts.get('summary')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
