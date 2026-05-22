"""Training pipeline helpers for Phase 7."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from qts.domain import Bar
from qts.features import FeaturePipeline, FeatureSpec

from .dataset import MLDataset, build_ml_dataset
from .leakage import validate_split_no_leakage
from .models import DirectionalModel, evaluate_directional_model, train_directional_model
from .registry import FileModelRegistry
from .splits import chronological_split
from .types import DatasetSplit


def train_directional_pipeline(
    bars: Sequence[Bar],
    *,
    model_id: str,
    feature_specs: Sequence[FeatureSpec | dict[str, Any]],
    feature_schema_version: str = "features_v1",
    horizon_bars: int = 1,
    up_threshold: float = 0.0,
    down_threshold: float = 0.0,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    embargo_bars: int = 1,
    decision_threshold: float = 0.55,
    registry: FileModelRegistry | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dataset, train a directional model, evaluate, and save it."""
    feature_pipeline = FeaturePipeline(
        feature_specs,
        schema_version=feature_schema_version,
        source="ml_training",
    )
    dataset = build_ml_dataset(
        bars,
        feature_pipeline=feature_pipeline,
        horizon_bars=horizon_bars,
        up_threshold=up_threshold,
        down_threshold=down_threshold,
    )
    split = chronological_split(
        dataset.samples,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        test_fraction=test_fraction,
        embargo_bars=embargo_bars,
    )
    validate_split_no_leakage(split)
    model = train_directional_model(
        split.train,
        model_id=model_id,
        feature_names=dataset.feature_names,
        feature_schema_version=dataset.feature_schema_version,
        decision_threshold=decision_threshold,
        metadata={
            "horizon": f"next_{horizon_bars}_bars",
            "label_config": dict(dataset.label_config),
            **dict(metadata or {}),
        },
    )
    metrics = {
        "train": evaluate_directional_model(model, split.train),
        "validation": evaluate_directional_model(model, split.validation),
        "test": evaluate_directional_model(model, split.test),
    }
    model = DirectionalModel(
        model_id=model.model_id,
        feature_names=model.feature_names,
        feature_schema_version=model.feature_schema_version,
        weights=model.weights,
        feature_means=model.feature_means,
        intercept=model.intercept,
        decision_threshold=model.decision_threshold,
        metadata=model.metadata,
        metrics=metrics,
        trained_at=model.trained_at,
    )
    registry = registry or FileModelRegistry()
    artifact_path = registry.save_model(model)
    return {
        "dataset": dataset,
        "split": split,
        "model": model,
        "metrics": metrics,
        "artifact_path": Path(artifact_path),
    }


__all__ = ["train_directional_pipeline"]
