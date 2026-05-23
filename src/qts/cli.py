"""Command-line entry point for lightweight project checks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="inspect and validate runtime configs")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    validate_parser = config_subparsers.add_parser("validate", help="validate a runtime config")
    validate_parser.add_argument("--config", required=True, help="runtime config path")
    dump_parser = config_subparsers.add_parser("dump", help="print the effective runtime config")
    dump_parser.add_argument("--config", required=True, help="runtime config path")
    dump_parser.add_argument("--format", choices=("json", "yaml"), default="json")
    explain_parser = config_subparsers.add_parser("explain", help="explain resolved config inputs")
    explain_parser.add_argument("--config", required=True, help="runtime config path")
    snippets_parser = config_subparsers.add_parser("list-snippets", help="list reusable config snippets")
    snippets_parser.add_argument("--config-root", default="configs", help="config root directory")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "config":
        return _config_command(args)

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


def _config_command(args: argparse.Namespace) -> int:
    if args.config_command == "list-snippets":
        return _list_snippets(args.config_root)
    try:
        config = load_runtime_config(args.config)
    except ConfigurationError as exc:
        print(f"configuration error: {exc}")
        return 2

    if args.config_command == "validate":
        print(f"valid {config.runtime_mode.value} config {config.run_id}")
        return 0
    if args.config_command == "dump":
        payload = _redact(config.to_dict())
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_to_yaml(payload))
        return 0
    if args.config_command == "explain":
        _explain_config(config)
        return 0
    print(f"unknown config command: {args.config_command}")
    return 2


def _list_snippets(config_root: str) -> int:
    root = Path(config_root)
    if not root.exists():
        print(f"configuration error: config root does not exist: {root}")
        return 2
    for directory in (root / "strategies", root / "risk"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            print(path)
    return 0


def _explain_config(config: Any) -> None:
    metadata = config.metadata
    print(f"run_id: {config.run_id}")
    print(f"mode: {config.runtime_mode.value}")
    print(f"config_file: {metadata.get('config_file', '<unknown>')}")
    print(f"project_root: {metadata.get('project_root', '<unknown>')}")
    if metadata.get("source_files"):
        print("source_files:")
        for source_file in metadata["source_files"]:
            print(f"  - {source_file}")
    print(f"market_data.path: {config.market_data.get('path')}")
    print(f"timeframe: {config.timeframe.value}")
    print(f"bar_interval: {config.bar_interval or '<not set>'}")
    print(f"adjustment: {config.market_data.get('adjustment', 'RAW')}")
    print("strategies:")
    for strategy in config.strategies:
        print(f"  - {strategy.strategy_id}: {strategy.strategy_type} {strategy.parameters}")
    try:
        from qts.engines.features import feature_pipeline_settings_from_strategies

        feature_specs, schema_version = feature_pipeline_settings_from_strategies(config.strategies)
        print(f"feature_schema_version: {schema_version}")
        for spec in feature_specs:
            print(f"  feature: {spec.name} {spec.parameters}")
    except ConfigurationError as exc:
        print(f"feature_plan_error: {exc}")
    print(f"risk: {config.risk.sizing_method} {config.risk.sizing_parameters}")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in ("secret", "token", "password")):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{_yaml_scalar(value)}"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


if __name__ == "__main__":
    raise SystemExit(main())
