#!/usr/bin/env python3
"""Generate report artifacts by running a local backtest."""

from __future__ import annotations

import argparse

from qts.workflows import generate_report_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/backtest_fixture.yaml")
    parser.add_argument("--output-dir", default="artifacts/reports")
    parser.add_argument("--env", default=".env")
    parser.add_argument(
        "--generate-plots",
        action="store_true",
        help="Write optional static SVG equity and drawdown chart artifacts.",
    )
    args = parser.parse_args(argv)

    result = generate_report_workflow(
        args.config,
        output_dir=args.output_dir,
        env_path=args.env,
        generate_plots=args.generate_plots,
    )
    print(f"generated report artifacts for {result.run_id}")
    for name, path in sorted(result.artifacts.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
