#!/usr/bin/env python3
"""Run a deterministic local backtest."""

from __future__ import annotations

import argparse

from qts.workflows import run_backtest_workflow


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

    result = run_backtest_workflow(args.config, output_dir=args.output_dir, env_path=args.env)
    print(
        f"backtest {result.run_id}: {len(result.fills)} fills, "
        f"total_return={result.metrics['total_return']:.6f}"
    )
    print(f"summary: {result.artifacts.get('summary')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
