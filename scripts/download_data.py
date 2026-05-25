#!/usr/bin/env python3
"""Download historical Alpaca SIP stock bars to normalized local files."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts.core import ConfigurationError, DataError
from qts.workflows import download_data_workflow


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
        result = download_data_workflow(
            args.config,
            env_path=args.env,
            symbols=args.symbols,
            timeframe=args.timeframe,
            start=args.start,
            end=args.end,
            output=args.output,
            output_format=args.format,
        )
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


if __name__ == "__main__":
    raise SystemExit(main())
