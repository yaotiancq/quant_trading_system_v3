#!/usr/bin/env python3
"""Download historical Alpaca SIP stock bars to normalized local files."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from qts.core import ConfigurationError, DataError, deep_merge, load_env_file, load_mapping_file
from qts.market_data import AlpacaBarDownloadConfig, download_alpaca_bars


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/data/alpaca_sip_bars.yaml",
        help="Alpaca SIP download config path",
    )
    parser.add_argument("--env", default=".env", help="optional .env path")
    parser.add_argument("--symbols", default=None, help="comma-separated symbol override")
    parser.add_argument("--timeframe", default=None, help="one of 1min, 5min, 15min, 1hour, 1day")
    parser.add_argument("--start", default=None, help="download start timestamp override")
    parser.add_argument("--end", default=None, help="download end timestamp override")
    parser.add_argument(
        "--output",
        default=None,
        help="output file path override for single-file configs or dataset directory for partitioned configs",
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=("csv", "parquet"),
        help="output format override",
    )
    args = parser.parse_args(argv)

    try:
        raw = load_mapping_file(args.config)
        overrides = _cli_overrides(args)
        if overrides:
            raw = deep_merge(raw, overrides)
        env_values = {**load_env_file(args.env), **os.environ}
        config = AlpacaBarDownloadConfig.from_mapping(raw, env_values=env_values)
        result = download_alpaca_bars(config)
    except (ConfigurationError, DataError, ValueError) as exc:
        print(f"data download failed: {exc}")
        return 2

    print(
        f"downloaded {result.row_count} Alpaca {result.feed.upper()} {result.timeframe} bars "
        f"for {','.join(result.symbols)} to {result.output_path} "
        f"as {result.output_format} {result.output_layout} output "
        f"({result.output_file_count} file(s)) "
        f"across {result.page_count} page(s)"
    )
    if result.filtered_row_count:
        print(
            f"session_filter_removed={result.filtered_row_count} "
            f"raw_rows={result.raw_row_count}"
        )
    if result.request_ids:
        print(f"alpaca_request_ids={','.join(result.request_ids)}")
    return 0


def _cli_overrides(args: argparse.Namespace) -> dict[str, object]:
    market_data: dict[str, object] = {}
    output: dict[str, object] = {}
    if args.symbols:
        market_data["symbols"] = [
            symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()
        ]
    if args.timeframe:
        market_data["timeframe"] = args.timeframe
    if args.start:
        market_data["start"] = args.start
    if args.end:
        market_data["end"] = args.end
    if args.output:
        output["path"] = args.output
    if args.format:
        output["format"] = args.format
    overrides: dict[str, object] = {}
    if market_data:
        overrides["market_data"] = market_data
    if output:
        overrides["output"] = output
    return overrides


if __name__ == "__main__":
    raise SystemExit(main())
