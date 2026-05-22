"""Command-line entry point for lightweight project checks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts import __version__
from qts.core import ConfigurationError, load_runtime_config


def main(argv: Sequence[str] | None = None) -> int:
    """Run a small Phase 1 CLI."""
    parser = argparse.ArgumentParser(prog="qts")
    parser.add_argument("--version", action="store_true", help="show package version")
    parser.add_argument(
        "--config",
        default=None,
        help="load and validate a runtime config, then print a short summary",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.config:
        try:
            config = load_runtime_config(args.config)
        except ConfigurationError as exc:
            print(f"configuration error: {exc}")
            return 2
        print(
            f"loaded {config.runtime_mode.value} config "
            f"{config.run_id} for {', '.join(config.symbols)}"
        )
        return 0

    print("qts Phase 1 foundation ready. Use --config configs/backtest.yaml to validate config.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
