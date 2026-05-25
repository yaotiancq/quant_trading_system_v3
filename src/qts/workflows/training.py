"""ML training workflow helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qts.core import (
    ConfigurationError,
    find_project_root,
    load_layered_mapping,
    resolve_project_path,
)
from qts.features import FeatureSpec
from qts.market_data import CSVBarProvider, LocalParquetProvider
from qts.ml import FileModelRegistry, train_directional_pipeline


def train_model_workflow(
    config_path: str | Path = "configs/ml/directional_baseline.yaml",
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Load an ML training config and train the directional baseline."""
    config_path = Path(config_path)
    project_root = find_project_root(config_path)
    raw = resolve_training_paths(load_layered_mapping(config_path), project_root)
    resolved_output_dir = (
        str(resolve_project_path(output_dir, project_root=project_root)) if output_dir else None
    )
    return train_from_mapping(raw, output_dir=resolved_output_dir)


def train_from_mapping(
    raw: Mapping[str, Any],
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Train the directional model from an already-loaded mapping."""
    model_config = _mapping(raw.get("model"), "model")
    market_data_config = _mapping(raw.get("market_data"), "market_data")
    feature_config = _mapping(raw.get("features"), "features")
    label_config = _mapping(raw.get("labels"), "labels")
    split_config = _mapping(raw.get("splits"), "splits")

    provider = provider_from_config(market_data_config)
    bars = provider.get_history(
        list(market_data_config.get("symbols") or []),
        market_data_config.get("start"),
        market_data_config.get("end"),
        market_data_config.get("timeframe"),
    )
    registry_dir = output_dir or str(model_config.get("registry_dir", "artifacts/models"))
    return train_directional_pipeline(
        bars,
        model_id=str(model_config["model_id"]),
        feature_specs=feature_specs(feature_config),
        feature_schema_version=str(feature_config.get("schema_version", "features_v1")),
        horizon_bars=int(label_config.get("horizon_bars", 1)),
        up_threshold=float(label_config.get("up_threshold", 0.0)),
        down_threshold=float(label_config.get("down_threshold", 0.0)),
        train_fraction=float(split_config.get("train_fraction", 0.6)),
        validation_fraction=float(split_config.get("validation_fraction", 0.2)),
        test_fraction=float(split_config.get("test_fraction", 0.2)),
        embargo_bars=int(split_config.get("embargo_bars", 1)),
        decision_threshold=float(model_config.get("decision_threshold", 0.55)),
        model_stage=str(model_config.get("stage", "candidate")),
        model_approved_by=model_config.get("approved_by"),
        model_approval_reason=model_config.get("approval_reason"),
        registry=FileModelRegistry(registry_dir),
        metadata={"training_config": dict(raw)},
    )


def provider_from_config(config: Mapping[str, Any]):
    """Create the historical provider for ML training."""
    provider_name = str(config.get("provider", "")).lower()
    path = config.get("path")
    if not path:
        raise ConfigurationError("market_data.path is required for ML training")
    if provider_name in {"csv", "local_csv", "fixture_csv"}:
        return CSVBarProvider(Path(path), default_timeframe=config.get("timeframe", "MINUTE"))
    if provider_name in {"parquet", "local_parquet"}:
        return LocalParquetProvider(Path(path), default_timeframe=config.get("timeframe", "MINUTE"))
    raise ConfigurationError(f"unsupported ML market data provider: {provider_name}")


def feature_specs(config: Mapping[str, Any]) -> list[FeatureSpec]:
    """Build feature specs from training config."""
    specs = []
    for item in list(config.get("specs") or []):
        item_mapping = _mapping(item, "feature spec")
        specs.append(
            FeatureSpec(
                name=str(item_mapping["name"]),
                parameters=dict(item_mapping.get("parameters") or {}),
            )
        )
    if not specs:
        raise ConfigurationError("features.specs must be non-empty")
    return specs


def resolve_training_paths(raw: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """Resolve training paths relative to the project root."""
    resolved = dict(raw)
    model = dict(resolved.get("model") or {})
    if model.get("registry_dir"):
        model["registry_dir"] = str(
            resolve_project_path(model["registry_dir"], project_root=project_root)
        )
    if model:
        resolved["model"] = model

    market_data = dict(resolved.get("market_data") or {})
    if market_data.get("path"):
        market_data["path"] = str(
            resolve_project_path(market_data["path"], project_root=project_root)
        )
    if market_data:
        resolved["market_data"] = market_data
    return resolved


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


_provider_from_config = provider_from_config
_feature_specs = feature_specs
_resolve_training_paths = resolve_training_paths


__all__ = [
    "feature_specs",
    "provider_from_config",
    "resolve_training_paths",
    "train_from_mapping",
    "train_model_workflow",
]
