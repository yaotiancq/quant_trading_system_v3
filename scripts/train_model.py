#!/usr/bin/env python3
"""Train the Phase 7 dependency-free directional ML baseline."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qts.core import (
    ConfigurationError,
    DataError,
    find_project_root,
    load_layered_mapping,
    resolve_project_path,
)
from qts.features import FeatureSpec
from qts.market_data import CSVBarProvider, LocalParquetProvider
from qts.ml import FileModelRegistry, MLWorkflowError, train_directional_pipeline


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/ml/directional_baseline.yaml",
        help="ML training config path",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override model registry output directory",
    )
    args = parser.parse_args(argv)

    try:
        config_path = Path(args.config)
        raw = _resolve_training_paths(load_layered_mapping(config_path), find_project_root(config_path))
        output_dir = (
            str(resolve_project_path(args.output_dir, project_root=find_project_root(config_path)))
            if args.output_dir
            else None
        )
        result = train_from_mapping(raw, output_dir=output_dir)
    except (ConfigurationError, DataError, MLWorkflowError, ValueError) as exc:
        print(f"model training failed: {exc}")
        return 2

    model = result["model"]
    metrics = result["metrics"]
    artifact_path = result["artifact_path"]
    manifest_path = result["manifest_path"]
    validation = metrics["validation"]
    print(
        f"trained model {model.model_id}: "
        f"samples={metrics['train']['sample_count'] + validation['sample_count'] + metrics['test']['sample_count']} "
        f"validation_accuracy={validation['accuracy']} "
        f"artifact={artifact_path} "
        f"manifest={manifest_path}"
    )
    return 0


def train_from_mapping(
    raw: Mapping[str, Any],
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    model_config = _mapping(raw.get("model"), "model")
    market_data_config = _mapping(raw.get("market_data"), "market_data")
    feature_config = _mapping(raw.get("features"), "features")
    label_config = _mapping(raw.get("labels"), "labels")
    split_config = _mapping(raw.get("splits"), "splits")

    provider = _provider_from_config(market_data_config)
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
        feature_specs=_feature_specs(feature_config),
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
        registry=FileModelRegistry(registry_dir),
        metadata={"training_config": dict(raw)},
    )


def _provider_from_config(config: Mapping[str, Any]):
    provider_name = str(config.get("provider", "")).lower()
    path = config.get("path")
    if not path:
        raise ConfigurationError("market_data.path is required for ML training")
    if provider_name in {"csv", "local_csv", "fixture_csv"}:
        return CSVBarProvider(Path(path), default_timeframe=config.get("timeframe", "MINUTE"))
    if provider_name in {"parquet", "local_parquet"}:
        return LocalParquetProvider(Path(path), default_timeframe=config.get("timeframe", "MINUTE"))
    raise ConfigurationError(f"unsupported ML market data provider: {provider_name}")


def _feature_specs(config: Mapping[str, Any]) -> list[FeatureSpec]:
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


def _resolve_training_paths(raw: dict[str, Any], project_root: Path) -> dict[str, Any]:
    resolved = dict(raw)
    model = dict(resolved.get("model") or {})
    if model.get("registry_dir"):
        model["registry_dir"] = str(resolve_project_path(model["registry_dir"], project_root=project_root))
    if model:
        resolved["model"] = model

    market_data = dict(resolved.get("market_data") or {})
    if market_data.get("path"):
        market_data["path"] = str(resolve_project_path(market_data["path"], project_root=project_root))
    if market_data:
        resolved["market_data"] = market_data
    return resolved


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
