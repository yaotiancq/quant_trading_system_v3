"""Historical data download workflow helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from qts.core import (
    deep_merge,
    find_project_root,
    load_env_file,
    load_layered_mapping,
    resolve_project_path,
)
from qts.market_data import AlpacaBarDownloadConfig, AlpacaBarDownloadResult, download_alpaca_bars


def download_data_workflow(
    config_path: str | Path = "configs/data/alpaca_sip_bars.yaml",
    *,
    env_path: str | Path = ".env",
    symbols: str | None = None,
    timeframe: str | None = None,
    start: str | None = None,
    end: str | None = None,
    output: str | None = None,
    output_format: str | None = None,
) -> AlpacaBarDownloadResult:
    """Load Alpaca download config and run the historical bar download."""
    config = build_alpaca_download_config(
        config_path,
        env_path=env_path,
        overrides=download_cli_overrides(
            symbols=symbols,
            timeframe=timeframe,
            start=start,
            end=end,
            output=output,
            output_format=output_format,
        ),
    )
    return download_alpaca_bars(config)


def build_alpaca_download_config(
    config_path: str | Path,
    *,
    env_path: str | Path = ".env",
    overrides: dict[str, object] | None = None,
) -> AlpacaBarDownloadConfig:
    """Build a validated Alpaca download config without starting a download."""
    config_path = Path(config_path)
    raw = load_layered_mapping(config_path)
    if overrides:
        raw = deep_merge(raw, overrides)
    raw = resolve_download_paths(raw, find_project_root(config_path))
    env_values = {**load_env_file(env_path), **os.environ}
    return AlpacaBarDownloadConfig.from_mapping(raw, env_values=env_values)


def download_cli_overrides(
    *,
    symbols: str | None = None,
    timeframe: str | None = None,
    start: str | None = None,
    end: str | None = None,
    output: str | None = None,
    output_format: str | None = None,
) -> dict[str, object]:
    """Translate CLI override values into layered config overrides."""
    market_data: dict[str, object] = {}
    output_config: dict[str, object] = {}
    if symbols:
        market_data["symbols"] = [
            symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()
        ]
    if timeframe:
        market_data["timeframe"] = timeframe
    if start:
        market_data["start"] = start
    if end:
        market_data["end"] = end
    if output:
        output_config["path"] = output
    if output_format:
        output_config["format"] = output_format
    overrides: dict[str, object] = {}
    if market_data:
        overrides["market_data"] = market_data
    if output_config:
        overrides["output"] = output_config
    return overrides


def resolve_download_paths(raw: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """Resolve configured output paths relative to the project root."""
    output = dict(raw.get("output") or {})
    for key in ("path", "directory"):
        if output.get(key):
            output[key] = str(resolve_project_path(output[key], project_root=project_root))
    if output:
        raw = dict(raw)
        raw["output"] = output
    return raw


__all__ = [
    "build_alpaca_download_config",
    "download_cli_overrides",
    "download_data_workflow",
    "resolve_download_paths",
]
