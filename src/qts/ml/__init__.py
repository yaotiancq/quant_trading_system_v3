"""Offline ML workflow and runtime inference utilities."""

from __future__ import annotations

from .dataset import MLDataset, build_ml_dataset
from .diagnostics import collect_strategy_ml_diagnostics, manifest_id, model_manifest_diagnostics
from .inference import DefaultMLModelInference
from .labels import build_forward_return_labels
from .leakage import validate_no_temporal_leakage, validate_split_no_leakage
from .models import DirectionalModel, evaluate_directional_model, train_directional_model
from .registry import FileModelRegistry
from .splits import chronological_split, walk_forward_splits
from .training import train_directional_pipeline
from .types import (
    DatasetSplit,
    ForwardReturnLabel,
    MLModelManifest,
    MLSample,
    MLWorkflowError,
    build_feature_schema_hash,
    normalize_model_stage,
)

__all__ = [
    "DatasetSplit",
    "DefaultMLModelInference",
    "DirectionalModel",
    "FileModelRegistry",
    "ForwardReturnLabel",
    "MLDataset",
    "MLModelManifest",
    "MLSample",
    "MLWorkflowError",
    "build_feature_schema_hash",
    "build_forward_return_labels",
    "build_ml_dataset",
    "collect_strategy_ml_diagnostics",
    "chronological_split",
    "evaluate_directional_model",
    "manifest_id",
    "model_manifest_diagnostics",
    "train_directional_model",
    "train_directional_pipeline",
    "validate_no_temporal_leakage",
    "validate_split_no_leakage",
    "walk_forward_splits",
    "normalize_model_stage",
]
