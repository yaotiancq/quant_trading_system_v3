"""Configuration loading and validation."""

from __future__ import annotations

import ast
import os
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
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
    path = Path(config_path).expanduser()
    raw, source_files = _load_layered_mapping(path)
    if overrides:
        raw = deep_merge(raw, dict(overrides))
        _preserve_explicit_sizing_parameters(raw, overrides)

    env_values = load_env_file(env_path) if env_path is not None else {}
    env_values = {**env_values, **os.environ}
    raw = interpolate_env_values(raw, env_values)
    project_root = find_project_root(path)
    raw, reference_sources = resolve_runtime_references(raw, config_path=path)
    raw = interpolate_env_values(raw, env_values)
    raw = resolve_runtime_paths(raw, project_root=project_root)
    metadata = {
        "config_file": str(path.resolve()),
        "config_dir": str(path.resolve().parent),
        "project_root": str(project_root),
        "source_files": [str(item) for item in _unique_paths([*source_files, *reference_sources])],
    }
    return build_runtime_config(raw, env_values=env_values, metadata=metadata)


def load_backtest_config(config_dir: str | Path = "configs") -> RuntimeConfig:
    return load_runtime_config(Path(config_dir) / "backtest.yaml")


def load_layered_mapping(path: str | Path) -> dict[str, Any]:
    data, _ = _load_layered_mapping(path)
    return data


def _load_layered_mapping(
    path: str | Path,
    *,
    _stack: tuple[Path, ...] = (),
) -> tuple[dict[str, Any], list[Path]]:
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigurationError(f"config file does not exist: {config_path}")
    resolved_path = config_path.resolve()
    if resolved_path in _stack:
        cycle = " -> ".join(str(item) for item in (*_stack, resolved_path))
        raise ConfigurationError(f"circular config extends detected: {cycle}")

    data = load_mapping_file(config_path)
    extends = data.pop("extends", None)
    if not extends:
        return data, [resolved_path]

    merged: dict[str, Any] = {}
    sources: list[Path] = []
    for include_path in _as_ref_list(extends, "extends"):
        base_path = resolve_config_reference(include_path, config_path=config_path)
        base, base_sources = _load_layered_mapping(base_path, _stack=(*_stack, resolved_path))
        merged = deep_merge(merged, base)
        sources.extend(base_sources)
    return deep_merge(merged, data), [*sources, resolved_path]


def load_mapping_file(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        return parse_yaml_mapping(text)
    raise ConfigurationError(f"unsupported config format: {config_path.suffix}")


def build_runtime_config(
    raw: Mapping[str, Any],
    *,
    env_values: Mapping[str, str],
    metadata: Mapping[str, Any] | None = None,
) -> RuntimeConfig:
    validate_runtime_mapping(raw)
    runtime = _mapping(raw.get("runtime"), "runtime")
    date_range = _mapping(raw.get("date_range"), "date_range", required=False)
    broker_raw = dict(_mapping(raw.get("broker"), "broker"))

    base_url_env = broker_raw.pop("base_url_env", None)
    if base_url_env and not broker_raw.get("base_url"):
        broker_raw["base_url"] = env_values.get(str(base_url_env))

    symbols = list(raw.get("symbols") or [])
    strategies = [_coerce_strategy_config(item, symbols) for item in list(raw.get("strategies") or [])]
    runtime_metadata = {
        "timezone": runtime.get("timezone", "UTC"),
        "project": dict(_mapping(raw.get("project"), "project", required=False)),
        "paths": dict(_mapping(raw.get("paths"), "paths", required=False)),
        "logging": dict(_mapping(raw.get("logging"), "logging", required=False)),
    }
    if metadata:
        runtime_metadata.update(dict(metadata))

    try:
        return RuntimeConfig(
            run_id=str(raw.get("run_id") or runtime.get("run_id") or _default_run_id(runtime)),
            runtime_mode=runtime.get("mode") or raw.get("runtime_mode"),
            symbols=symbols,
            start=date_range.get("start") or raw.get("start"),
            end=date_range.get("end") or raw.get("end"),
            timeframe=raw.get("timeframe"),
            bar_interval=raw.get("bar_interval") or raw.get("market_data", {}).get("bar_interval"),
            market_data=dict(_mapping(raw.get("market_data"), "market_data")),
            broker=BrokerConfig(**broker_raw),
            strategies=strategies,
            risk=dict(_mapping(raw.get("risk"), "risk")),
            portfolio=dict(_mapping(raw.get("portfolio"), "portfolio")),
            execution=dict(_mapping(raw.get("execution"), "execution")),
            market_session=dict(_mapping(raw.get("market_session"), "market_session", required=False)),
            reporting=dict(_mapping(raw.get("reporting"), "reporting", required=False)),
            monitoring=dict(_mapping(raw.get("monitoring"), "monitoring", required=False)),
            metadata=runtime_metadata,
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


ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def interpolate_env_values(value: Any, env_values: Mapping[str, str]) -> Any:
    """Recursively expand ${VAR} and ${VAR:-default} in config values."""
    if isinstance(value, str):
        return _interpolate_env_string(value, env_values)
    if isinstance(value, Mapping):
        return {key: interpolate_env_values(item, env_values) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate_env_values(item, env_values) for item in value]
    return value


def resolve_runtime_references(
    raw: Mapping[str, Any],
    *,
    config_path: str | Path,
) -> tuple[dict[str, Any], list[Path]]:
    """Resolve runtime strategy and risk snippet references into an effective mapping."""
    config_file = Path(config_path).expanduser()
    resolved = deepcopy(dict(raw))
    source_files: list[Path] = []

    strategies = []
    for item in list(resolved.get("strategies") or []):
        if not isinstance(item, Mapping) or "config_ref" not in item:
            strategies.append(item)
            continue
        ref_path = resolve_config_reference(str(item["config_ref"]), config_path=config_file)
        snippet, snippet_sources = _load_layered_mapping(ref_path)
        overrides = dict(item)
        overrides.pop("config_ref", None)
        strategies.append(deep_merge(snippet, overrides))
        source_files.extend(snippet_sources)
    if "strategies" in resolved:
        resolved["strategies"] = strategies

    risk_ref = resolved.pop("risk_ref", None)
    risk = resolved.get("risk")
    if isinstance(risk, Mapping) and "config_ref" in risk:
        risk_ref = risk.get("config_ref")
        risk = {key: value for key, value in risk.items() if key != "config_ref"}
    if risk_ref:
        ref_path = resolve_config_reference(str(risk_ref), config_path=config_file)
        snippet, snippet_sources = _load_layered_mapping(ref_path)
        overrides = dict(risk) if isinstance(risk, Mapping) else {}
        merged_risk = deep_merge(snippet, overrides)
        if "sizing_parameters" in overrides:
            merged_risk["sizing_parameters"] = overrides["sizing_parameters"]
        resolved["risk"] = merged_risk
        source_files.extend(snippet_sources)

    return resolved, _unique_paths(source_files)


def _preserve_explicit_sizing_parameters(raw: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    risk_override = overrides.get("risk")
    if not isinstance(risk_override, Mapping) or "sizing_parameters" not in risk_override:
        return
    risk = raw.get("risk")
    if isinstance(risk, dict):
        risk["sizing_parameters"] = risk_override["sizing_parameters"]


def _unique_paths(paths: Sequence[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def resolve_runtime_paths(raw: Mapping[str, Any], *, project_root: Path) -> dict[str, Any]:
    """Resolve runtime file-system paths against the discovered project root."""
    resolved = deepcopy(dict(raw))
    market_data = resolved.get("market_data")
    if isinstance(market_data, Mapping) and market_data.get("path"):
        updated = dict(market_data)
        updated["path"] = str(resolve_project_path(updated["path"], project_root=project_root))
        resolved["market_data"] = updated

    reporting = resolved.get("reporting")
    if isinstance(reporting, Mapping) and reporting.get("output_dir"):
        updated = dict(reporting)
        updated["output_dir"] = str(resolve_project_path(updated["output_dir"], project_root=project_root))
        resolved["reporting"] = updated

    paths = resolved.get("paths")
    if isinstance(paths, Mapping):
        resolved["paths"] = {
            key: str(resolve_project_path(value, project_root=project_root))
            for key, value in paths.items()
        }
    return resolved


def resolve_project_path(value: Any, *, project_root: Path) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else (project_root / path).resolve()


def find_project_root(config_path: str | Path) -> Path:
    """Find the repository/project root for a config file."""
    start = Path(config_path).expanduser().resolve()
    for parent in (start.parent, *start.parents):
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists():
            return parent
    if start.parent.name == "configs":
        return start.parent.parent
    return start.parent


def resolve_config_reference(reference: str, *, config_path: Path) -> Path:
    ref_path = Path(reference).expanduser()
    if ref_path.is_absolute():
        candidate = ref_path
    else:
        candidate = config_path.parent / ref_path
    if not candidate.is_file():
        raise ConfigurationError(f"referenced config file does not exist: {candidate}")
    return candidate


def validate_runtime_mapping(raw: Mapping[str, Any]) -> None:
    """Validate runtime config keys before building dataclasses."""
    _reject_unknown_keys(
        raw,
        {
            "project",
            "paths",
            "logging",
            "metadata",
            "run_id",
            "runtime",
            "runtime_mode",
            "symbols",
            "timeframe",
            "bar_interval",
            "date_range",
            "start",
            "end",
            "market_data",
            "broker",
            "strategies",
            "risk",
            "portfolio",
            "execution",
            "market_session",
            "reporting",
            "monitoring",
        },
        "runtime config",
    )
    _reject_unknown_keys(_mapping(raw.get("runtime"), "runtime"), {"mode", "timezone", "run_id"}, "runtime")
    runtime = _mapping(raw.get("runtime"), "runtime")
    if not runtime.get("mode"):
        raise ConfigurationError("runtime.mode is required in active runtime configs")
    if not raw.get("symbols"):
        raise ConfigurationError("symbols must be explicitly configured in active runtime configs")
    if not raw.get("timeframe"):
        raise ConfigurationError("timeframe must be explicitly configured in active runtime configs")
    _reject_unknown_keys(
        _mapping(raw.get("date_range"), "date_range", required=False),
        {"start", "end"},
        "date_range",
    )
    _validate_market_data(_mapping(raw.get("market_data"), "market_data"))
    _validate_broker(_mapping(raw.get("broker"), "broker"))
    _validate_portfolio(_mapping(raw.get("portfolio"), "portfolio"))
    _validate_execution(_mapping(raw.get("execution"), "execution"))
    _validate_market_session(_mapping(raw.get("market_session"), "market_session", required=False))
    _validate_reporting(_mapping(raw.get("reporting"), "reporting", required=False))
    _validate_monitoring(_mapping(raw.get("monitoring"), "monitoring", required=False))
    _validate_risk(_mapping(raw.get("risk"), "risk"))
    _validate_strategies(list(raw.get("strategies") or []))
    _validate_mode_specific(raw)


def _interpolate_env_string(value: str, env_values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2)
        if key in env_values:
            return env_values[key]
        if default is not None:
            return default
        raise ConfigurationError(f"required environment variable is missing: {key}")

    return ENV_PATTERN.sub(replace, value)


def _as_ref_list(value: Any, field_name: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        refs = [str(item) for item in value]
        if refs:
            return refs
    raise ConfigurationError(f"{field_name} must be a path string or non-empty list of paths")


def _reject_unknown_keys(mapping: Mapping[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(str(key) for key in mapping if key not in allowed)
    if unknown:
        raise ConfigurationError(f"unknown {section} field(s): {', '.join(unknown)}")


def _validate_market_data(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(
        config,
        {
            "provider",
            "path",
            "adjustment",
            "bar_interval",
            "events",
            "event_types",
            "feed",
            "max_staleness_seconds",
            "mock_messages",
            "session_filter",
            "symbols",
            "deduplicate",
            "fail_on_out_of_order",
        },
        "market_data",
    )
    if "event_types" in config:
        event_types = config["event_types"]
        if not isinstance(event_types, Sequence) or isinstance(event_types, (str, bytes, bytearray)):
            raise ConfigurationError("market_data.event_types must be a list")
        allowed = {"bars", "quotes"}
        unknown = sorted(str(item) for item in event_types if str(item).lower() not in allowed)
        if unknown:
            raise ConfigurationError(
                f"unsupported market_data.event_types value(s): {', '.join(unknown)}"
            )
    if "max_staleness_seconds" in config and config["max_staleness_seconds"] is not None:
        if float(config["max_staleness_seconds"]) < 0:
            raise ConfigurationError("market_data.max_staleness_seconds must be non-negative")
    if "events" in config:
        events = config["events"]
        if not isinstance(events, Sequence) or isinstance(events, (str, bytes, bytearray)):
            raise ConfigurationError("market_data.events must be a list")
    if "mock_messages" in config:
        messages = config["mock_messages"]
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes, bytearray)):
            raise ConfigurationError("market_data.mock_messages must be a list")
    if "symbols" in config:
        symbols = config["symbols"]
        if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes, bytearray)):
            raise ConfigurationError("market_data.symbols must be a list")
    if "feed" in config:
        feed = str(config["feed"]).lower()
        if feed not in {"iex", "sip"}:
            raise ConfigurationError("market_data.feed must be iex or sip")


def _validate_broker(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(
        config,
        {
            "broker_type",
            "account_id",
            "paper",
            "base_url",
            "base_url_env",
            "credential_env_keys",
            "commission_model",
            "slippage_model",
            "fill_policy",
            "safety",
        },
        "broker",
    )
    credential_keys = _mapping(config.get("credential_env_keys"), "broker.credential_env_keys", required=False)
    _reject_unknown_keys(credential_keys, {"api_key_id", "secret_key", "access_token"}, "broker.credential_env_keys")
    for model_name in ("commission_model", "slippage_model"):
        model = _mapping(config.get(model_name), f"broker.{model_name}", required=False)
        _reject_unknown_keys(model, {"type", "value"}, f"broker.{model_name}")
    safety = _mapping(config.get("safety"), "broker.safety", required=False)
    _reject_unknown_keys(
        safety,
        {
            "mock_mode",
            "require_paper",
            "live_enabled",
            "confirm_live_trading",
            "dry_run",
            "dry_run_account_id",
            "dry_run_cash",
            "require_account_allowlist",
            "allowed_account_ids",
            "require_symbol_allowlist",
            "allowed_symbols",
            "max_order_notional",
            "max_order_quantity",
            "symbol_conids",
        },
        "broker.safety",
    )


def _validate_portfolio(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(config, {"starting_cash", "currency", "account_id"}, "portfolio")
    if "starting_cash" in config and float(config["starting_cash"]) <= 0:
        raise ConfigurationError("portfolio.starting_cash must be positive")


def _validate_execution(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(config, {"allow_fractional"}, "execution")


def _validate_market_session(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(
        config,
        {
            "exchange",
            "timezone",
            "regular_session_only",
            "extended_hours",
            "fail_closed",
            "calendar_provider",
            "regular_open",
            "regular_close",
        },
        "market_session",
    )
    extended = config.get("extended_hours")
    if isinstance(extended, Mapping):
        _reject_unknown_keys(
            extended,
            {"enabled", "premarket_open", "after_hours_close"},
            "market_session.extended_hours",
        )
    if config:
        from qts.calendar import market_session_config_from_mapping

        market_session_config_from_mapping(config)


def _validate_reporting(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(
        config,
        {
            "output_dir",
            "generate_plots",
            "annualization_factor",
            "risk_free_rate",
        },
        "reporting",
    )


def _validate_monitoring(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(config, {"enabled"}, "monitoring")


def _validate_risk(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(
        config,
        {
            "sizing_method",
            "sizing_parameters",
            "max_position_notional",
            "max_gross_exposure",
            "max_symbol_weight",
            "daily_loss_limit",
            "allowed_symbols",
            "blocked_symbols",
            "cooldown_seconds",
            "session_rules",
            "disabled_until_configured",
        },
        "risk",
    )
    params = _mapping(config.get("sizing_parameters"), "risk.sizing_parameters", required=False)
    method = str(config.get("sizing_method") or "").lower()
    disabled = bool(config.get("disabled_until_configured", False))
    if method == "fixed_quantity":
        _reject_unknown_keys(params, {"quantity", "quantity_per_trade"}, "risk.sizing_parameters")
        _require_positive_sizing_value(params, ("quantity", "quantity_per_trade"), method, disabled)
    elif method in {"fixed_notional", "fixed_dollar"}:
        _reject_unknown_keys(params, {"notional_per_trade", "notional"}, "risk.sizing_parameters")
        _require_positive_sizing_value(params, ("notional_per_trade", "notional"), method, disabled)
    elif method in {"percent_equity", "percent_of_equity"}:
        _reject_unknown_keys(params, {"percent", "percent_of_equity"}, "risk.sizing_parameters")
        value = _require_positive_sizing_value(params, ("percent", "percent_of_equity"), method, disabled)
        if value is not None and value > 1.0:
            raise ConfigurationError("percent_equity sizing percent must be <= 1.0")
    else:
        raise ConfigurationError(f"unsupported risk.sizing_method: {config.get('sizing_method')}")
    session_rules = _mapping(config.get("session_rules"), "risk.session_rules", required=False)
    _reject_unknown_keys(session_rules, {"enabled", "market_open", "market_close", "weekdays"}, "risk.session_rules")


def _validate_strategies(strategies: list[Any]) -> None:
    if not strategies:
        raise ConfigurationError("strategies must contain at least one strategy")
    for index, item in enumerate(strategies):
        if not isinstance(item, Mapping):
            raise ConfigurationError(f"strategies[{index}] must be a mapping")
        _reject_unknown_keys(
            item,
            {"strategy_id", "strategy_type", "symbols", "enabled", "parameters", "feature_config"},
            f"strategies[{index}]",
        )
        strategy_type = str(item.get("strategy_type") or "").lower()
        parameters = _mapping(item.get("parameters"), f"strategies[{index}].parameters", required=False)
        if strategy_type in {"sma_crossover", "sma_cross"}:
            _reject_unknown_keys(parameters, {"fast_window", "slow_window"}, f"strategies[{index}].parameters")
        elif strategy_type in {"rsi_mean_reversion", "rsi_reversion"}:
            _reject_unknown_keys(parameters, {"window", "oversold", "overbought"}, f"strategies[{index}].parameters")
        elif strategy_type in {"ml_signal", "ml_directional", "ml_direction"}:
            _reject_unknown_keys(
                parameters,
                {"model_id", "registry_dir", "buy_probability_threshold", "sell_probability_threshold"},
                f"strategies[{index}].parameters",
            )
        else:
            raise ConfigurationError(f"unsupported strategy_type: {item.get('strategy_type')}")
        _validate_feature_config(
            _mapping(item.get("feature_config"), f"strategies[{index}].feature_config", required=False),
            index,
        )


def _validate_feature_config(config: Mapping[str, Any], strategy_index: int) -> None:
    _reject_unknown_keys(
        config,
        {"schema_version", "specs"},
        f"strategies[{strategy_index}].feature_config",
    )
    specs = config.get("specs")
    if specs is None:
        return
    if not isinstance(specs, Sequence) or isinstance(specs, (str, bytes, bytearray)):
        raise ConfigurationError(f"strategies[{strategy_index}].feature_config.specs must be a list")
    for spec_index, spec in enumerate(specs):
        if not isinstance(spec, Mapping):
            raise ConfigurationError(
                f"strategies[{strategy_index}].feature_config.specs[{spec_index}] must be a mapping"
            )
        _reject_unknown_keys(
            spec,
            {"name", "parameters"},
            f"strategies[{strategy_index}].feature_config.specs[{spec_index}]",
        )


def _validate_mode_specific(raw: Mapping[str, Any]) -> None:
    runtime = _mapping(raw.get("runtime"), "runtime")
    mode = str(runtime.get("mode") or raw.get("runtime_mode") or "").upper()
    market_data = _mapping(raw.get("market_data"), "market_data")
    broker = _mapping(raw.get("broker"), "broker")
    _validate_fractional_sizing_compatibility(raw)
    if mode == "BACKTEST":
        if not raw.get("start") and not _mapping(raw.get("date_range"), "date_range", required=False).get("start"):
            raise ConfigurationError("BACKTEST configs require date_range.start")
        if not raw.get("end") and not _mapping(raw.get("date_range"), "date_range", required=False).get("end"):
            raise ConfigurationError("BACKTEST configs require date_range.end")
        if not market_data.get("path"):
            raise ConfigurationError("BACKTEST configs require market_data.path")
        if str(broker.get("broker_type") or "").lower() != "backtest":
            raise ConfigurationError("BACKTEST configs require broker.broker_type=backtest")
        provider = str(market_data.get("provider") or "").lower()
        if provider not in {"csv", "local_csv", "fixture_csv", "parquet", "local_parquet"}:
            raise ConfigurationError(f"unsupported BACKTEST market_data.provider: {provider}")
    elif mode == "PAPER":
        broker_type = str(broker.get("broker_type") or "").lower()
        if broker_type not in {"alpaca_paper", "ibkr_paper"}:
            raise ConfigurationError("PAPER configs require broker.broker_type=alpaca_paper or ibkr_paper")
        provider = str(market_data.get("provider") or "").lower()
        if provider not in {
            "external_events",
            "fake_stream",
            "alpaca_stream",
            "alpaca_sip_stream",
            "alpaca_iex_stream",
        }:
            raise ConfigurationError(
                "PAPER configs require market_data.provider=external_events, "
                "fake_stream, or alpaca_stream"
            )
        if provider == "fake_stream" and "events" not in market_data:
            raise ConfigurationError("PAPER fake_stream configs require market_data.events")
    elif mode == "LIVE":
        if str(broker.get("broker_type") or "").lower() != "alpaca_live":
            raise ConfigurationError("LIVE configs currently require broker.broker_type=alpaca_live")
        if str(market_data.get("provider") or "").lower() != "external_events":
            raise ConfigurationError("LIVE configs currently require market_data.provider=external_events")
    else:
        raise ConfigurationError(f"unsupported runtime.mode: {mode}")


def _validate_fractional_sizing_compatibility(raw: Mapping[str, Any]) -> None:
    execution = _mapping(raw.get("execution"), "execution")
    if bool(execution.get("allow_fractional", True)):
        return
    risk = _mapping(raw.get("risk"), "risk")
    if bool(risk.get("disabled_until_configured", False)):
        return
    method = str(risk.get("sizing_method") or "").lower()
    if method in {"fixed_notional", "fixed_dollar", "percent_equity", "percent_of_equity"}:
        raise ConfigurationError(
            "execution.allow_fractional=false requires quantity-based sizing; "
            f"{method} produces notional orders"
        )


def _require_positive_sizing_value(
    params: Mapping[str, Any],
    keys: tuple[str, ...],
    method: str,
    disabled_until_configured: bool,
) -> float | None:
    for key in keys:
        if key in params:
            value = float(params[key])
            if value <= 0 and not disabled_until_configured:
                raise ConfigurationError(f"{method} sizing requires positive {key}")
            return value
    if disabled_until_configured:
        return None
    expected = " or ".join(keys)
    raise ConfigurationError(f"{method} sizing requires {expected}")


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
    "find_project_root",
    "interpolate_env_values",
    "load_backtest_config",
    "load_env_file",
    "load_layered_mapping",
    "load_mapping_file",
    "load_runtime_config",
    "parse_yaml_mapping",
    "require_env_value",
    "resolve_config_reference",
    "resolve_project_path",
    "resolve_runtime_paths",
    "resolve_runtime_references",
    "validate_runtime_mapping",
]
