"""Configuration loading and validation."""

from __future__ import annotations

import ast
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qts.domain import BrokerConfig, RuntimeConfig, StrategyConfig

from .exceptions import ConfigurationError


def load_runtime_config(
    config_path: str | Path,
    *,
    env_path: str | Path | None = ".env",
    overrides: Mapping[str, Any] | None = None,
) -> RuntimeConfig:
    """Load a layered runtime configuration and return a validated model."""
    path = Path(config_path)
    raw = load_layered_mapping(path)
    if overrides:
        raw = deep_merge(raw, dict(overrides))

    env_values = load_env_file(env_path) if env_path is not None else {}
    env_values = {**env_values, **os.environ}
    return build_runtime_config(raw, env_values=env_values)


def load_backtest_config(config_dir: str | Path = "configs") -> RuntimeConfig:
    return load_runtime_config(Path(config_dir) / "backtest.yaml")


def load_layered_mapping(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(f"config file does not exist: {config_path}")

    data = load_mapping_file(config_path)
    extends = data.pop("extends", None)
    if extends:
        base_path = config_path.parent / str(extends)
        base = load_layered_mapping(base_path)
        return deep_merge(base, data)
    return data


def load_mapping_file(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        return parse_yaml_mapping(text)
    raise ConfigurationError(f"unsupported config format: {config_path.suffix}")


def build_runtime_config(raw: Mapping[str, Any], *, env_values: Mapping[str, str]) -> RuntimeConfig:
    runtime = _mapping(raw.get("runtime"), "runtime")
    date_range = _mapping(raw.get("date_range"), "date_range", required=False)
    broker_raw = dict(_mapping(raw.get("broker"), "broker"))

    base_url_env = broker_raw.pop("base_url_env", None)
    if base_url_env and not broker_raw.get("base_url"):
        broker_raw["base_url"] = env_values.get(str(base_url_env))

    symbols = list(raw.get("symbols") or [])
    strategies = [_coerce_strategy_config(item, symbols) for item in list(raw.get("strategies") or [])]

    try:
        return RuntimeConfig(
            run_id=str(raw.get("run_id") or runtime.get("run_id") or _default_run_id(runtime)),
            runtime_mode=runtime.get("mode") or raw.get("runtime_mode"),
            symbols=symbols,
            start=date_range.get("start") or raw.get("start"),
            end=date_range.get("end") or raw.get("end"),
            timeframe=raw.get("timeframe"),
            market_data=dict(_mapping(raw.get("market_data"), "market_data")),
            broker=BrokerConfig(**broker_raw),
            strategies=strategies,
            risk=dict(_mapping(raw.get("risk"), "risk")),
            portfolio=dict(_mapping(raw.get("portfolio"), "portfolio")),
            execution=dict(_mapping(raw.get("execution"), "execution")),
            reporting=dict(_mapping(raw.get("reporting"), "reporting", required=False)),
            monitoring=dict(_mapping(raw.get("monitoring"), "monitoring", required=False)),
            metadata={"timezone": runtime.get("timezone", "UTC")},
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(str(exc)) from exc


def require_env_value(key: str, *, env_values: Mapping[str, str] | None = None) -> str:
    env = os.environ if env_values is None else env_values
    value = env.get(key)
    if not value:
        raise ConfigurationError(f"required environment variable is missing: {key}")
    return value


def load_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ConfigurationError(f"invalid .env line {line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigurationError(f"invalid .env line {line_number}: empty key")
        values[key] = _strip_quotes(value.strip())
    return values


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def parse_yaml_mapping(text: str) -> dict[str, Any]:
    """Parse a small YAML subset, preferring PyYAML when it is installed."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        parsed = _parse_simple_yaml(text)
    else:
        try:
            loaded = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ConfigurationError(f"invalid YAML: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigurationError("top-level YAML document must be a mapping")
        parsed = loaded

    if not isinstance(parsed, dict):
        raise ConfigurationError("top-level YAML document must be a mapping")
    return parsed


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    lines = _preprocess_yaml_lines(text)
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ConfigurationError("could not parse complete YAML document")
    if not isinstance(value, dict):
        raise ConfigurationError("top-level YAML document must be a mapping")
    return value


def _preprocess_yaml_lines(text: str) -> list[tuple[int, str]]:
    processed: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        without_comments = raw_line.split("#", 1)[0].rstrip()
        if not without_comments.strip():
            continue
        indent = len(without_comments) - len(without_comments.lstrip(" "))
        if "\t" in without_comments[:indent]:
            raise ConfigurationError("YAML indentation must use spaces")
        processed.append((indent, without_comments.strip()))
    return processed


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index][0] < indent:
        return {}, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ConfigurationError(f"unexpected indentation before {text!r}")
        if text.startswith("- "):
            break
        key, value_text = _split_key_value(text)
        index += 1
        if value_text:
            result[key] = _parse_scalar(value_text)
        elif index < len(lines) and lines[index][0] > indent:
            result[key], index = _parse_block(lines, index, lines[index][0])
        else:
            result[key] = {}
    return result, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not text.startswith("- "):
            break

        item_text = text[2:].strip()
        index += 1
        if not item_text:
            if index < len(lines) and lines[index][0] > indent:
                item, index = _parse_block(lines, index, lines[index][0])
            else:
                item = None
        elif _looks_like_mapping_item(item_text):
            key, value_text = _split_key_value(item_text)
            item = {key: _parse_scalar(value_text) if value_text else {}}
            if index < len(lines) and lines[index][0] > indent:
                nested, index = _parse_block(lines, index, lines[index][0])
                if isinstance(nested, dict):
                    item.update(nested)
                else:
                    raise ConfigurationError("list mapping item cannot contain a nested list here")
        else:
            item = _parse_scalar(item_text)
        result.append(item)
    return result, index


def _split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ConfigurationError(f"expected key-value pair, got {text!r}")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ConfigurationError("mapping key cannot be empty")
    return key, value.strip()


def _looks_like_mapping_item(text: str) -> bool:
    if ":" not in text:
        return False
    key, _ = text.split(":", 1)
    return bool(key.strip()) and " " not in key.strip()


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    lowered = text.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text in {"[]", "{}"}:
        return ast.literal_eval(text)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if text.startswith("{") and text.endswith("}"):
        try:
            return ast.literal_eval(text)
        except (SyntaxError, ValueError) as exc:
            raise ConfigurationError(f"unsupported inline mapping: {text!r}") from exc
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return _strip_quotes(text)
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _strip_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _mapping(value: Any, name: str, *, required: bool = True) -> Mapping[str, Any]:
    if value is None:
        if required:
            raise ConfigurationError(f"missing required config section: {name}")
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def _coerce_strategy_config(item: Any, symbols: list[str]) -> StrategyConfig:
    if isinstance(item, str):
        return StrategyConfig(
            strategy_id=item,
            strategy_type=item,
            symbols=symbols,
            parameters={},
            enabled=True,
        )
    if isinstance(item, Mapping):
        return StrategyConfig(**dict(item))
    raise ConfigurationError("strategy entries must be mappings or string identifiers")


def _default_run_id(runtime: Mapping[str, Any]) -> str:
    mode = str(runtime.get("mode") or "run").lower()
    return f"{mode}-default"


__all__ = [
    "build_runtime_config",
    "deep_merge",
    "load_backtest_config",
    "load_env_file",
    "load_layered_mapping",
    "load_mapping_file",
    "load_runtime_config",
    "parse_yaml_mapping",
    "require_env_value",
]
