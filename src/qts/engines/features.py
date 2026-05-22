"""Shared feature-pipeline configuration for runtime engines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from qts.core import ConfigurationError
from qts.domain import StrategyConfig
from qts.features import FeatureSpec


DEFAULT_FEATURE_SCHEMA_VERSION = "features_v1"


def feature_pipeline_settings_from_strategies(
    strategy_configs: Sequence[StrategyConfig],
) -> tuple[list[FeatureSpec], str]:
    """Return deduplicated feature specs and one schema version for enabled strategies."""
    specs: list[FeatureSpec] = []
    seen: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
    schema_versions: set[str] = set()
    for config in strategy_configs:
        if not config.enabled:
            continue
        schema_version = _feature_schema_version(config)
        if schema_version is not None:
            schema_versions.add(schema_version)
        for spec in feature_specs_for_strategy(config):
            key = (spec.name, tuple(sorted(spec.parameters.items())))
            if key not in seen:
                specs.append(spec)
                seen.add(key)
    if len(schema_versions) > 1:
        joined = ", ".join(sorted(schema_versions))
        raise ConfigurationError(f"conflicting feature schema versions: {joined}")
    schema_version = next(iter(schema_versions), DEFAULT_FEATURE_SCHEMA_VERSION)
    return specs, schema_version


def feature_specs_for_strategy(config: StrategyConfig) -> list[FeatureSpec]:
    """Resolve feature specs from explicit strategy config or built-in rule strategy defaults."""
    explicit_specs = _explicit_feature_specs(config)
    if explicit_specs is not None:
        return explicit_specs

    strategy_type = config.strategy_type.lower()
    params = dict(config.parameters)
    if strategy_type in {"sma_crossover", "sma_cross"}:
        return [
            FeatureSpec("sma", {"window": int(params.get("fast_window", 20))}),
            FeatureSpec("sma", {"window": int(params.get("slow_window", 50))}),
        ]
    if strategy_type in {"rsi_mean_reversion", "rsi_reversion"}:
        return [FeatureSpec("rsi", {"window": int(params.get("window", 14))})]
    return []


def _feature_schema_version(config: StrategyConfig) -> str | None:
    feature_config = config.feature_config or {}
    value = feature_config.get("schema_version") or config.parameters.get("feature_schema_version")
    return str(value) if value else None


def _explicit_feature_specs(config: StrategyConfig) -> list[FeatureSpec] | None:
    feature_config = config.feature_config or {}
    raw_specs = feature_config.get("specs", config.parameters.get("feature_specs"))
    if raw_specs is None:
        return None
    if not isinstance(raw_specs, Sequence) or isinstance(raw_specs, (str, bytes)):
        raise ConfigurationError(f"feature specs for {config.strategy_id} must be a list")
    return [_coerce_feature_spec(config.strategy_id, item) for item in raw_specs]


def _coerce_feature_spec(strategy_id: str, item: Any) -> FeatureSpec:
    if isinstance(item, FeatureSpec):
        return item
    if not isinstance(item, Mapping):
        raise ConfigurationError(f"feature spec for {strategy_id} must be a mapping")
    name = item.get("name")
    if not name:
        raise ConfigurationError(f"feature spec for {strategy_id} is missing name")
    parameters = item.get("parameters") or {}
    if not isinstance(parameters, Mapping):
        raise ConfigurationError(f"feature spec parameters for {strategy_id} must be a mapping")
    return FeatureSpec(str(name), dict(parameters))


__all__ = [
    "DEFAULT_FEATURE_SCHEMA_VERSION",
    "feature_pipeline_settings_from_strategies",
    "feature_specs_for_strategy",
]
