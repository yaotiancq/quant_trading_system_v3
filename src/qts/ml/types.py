"""Shared ML workflow types."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qts.domain import normalize_symbol, normalize_timestamp


class MLWorkflowError(Exception):
    """Raised for controlled ML workflow failures."""


MODEL_MANIFEST_VERSION = "ml_model_manifest_v1"
MODEL_STAGES = {"candidate", "validated", "approved", "archived", "legacy"}


@dataclass(frozen=True)
class MLModelManifest:
    """Portable metadata contract for a registered ML model artifact."""

    model_id: str
    model_type: str
    model_artifact: str
    feature_schema_version: str
    feature_names: list[str]
    feature_schema_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    manifest_version: str = MODEL_MANIFEST_VERSION
    stage: str = "candidate"
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.model_id).strip():
            raise ValueError("model_id must be non-empty")
        if not str(self.model_type).strip():
            raise ValueError("model_type must be non-empty")
        if not str(self.model_artifact).strip():
            raise ValueError("model_artifact must be non-empty")
        if not str(self.feature_schema_version).strip():
            raise ValueError("feature_schema_version must be non-empty")
        if not self.feature_names:
            raise ValueError("feature_names must be non-empty")
        stage = str(self.stage).lower()
        if stage not in MODEL_STAGES:
            raise ValueError(f"unsupported model stage: {self.stage}")
        expected_hash = build_feature_schema_hash(self.feature_schema_version, self.feature_names)
        if self.feature_schema_hash != expected_hash:
            raise ValueError("feature_schema_hash does not match feature schema")
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_type", str(self.model_type))
        object.__setattr__(self, "model_artifact", str(self.model_artifact))
        object.__setattr__(self, "feature_schema_version", str(self.feature_schema_version))
        object.__setattr__(self, "feature_names", [str(name) for name in self.feature_names])
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))
        object.__setattr__(self, "manifest_version", str(self.manifest_version))
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def from_model(
        cls,
        model: Any,
        *,
        model_artifact: str,
        stage: str = "candidate",
        metadata: dict[str, Any] | None = None,
    ) -> "MLModelManifest":
        """Build a manifest from a dependency-free model object."""
        feature_names = [str(name) for name in model.feature_names]
        return cls(
            model_id=str(model.model_id),
            model_type=str(model.to_dict().get("model_type")),
            model_artifact=model_artifact,
            feature_schema_version=str(model.feature_schema_version),
            feature_names=feature_names,
            feature_schema_hash=build_feature_schema_hash(
                str(model.feature_schema_version),
                feature_names,
            ),
            created_at=normalize_timestamp(model.trained_at),
            stage=stage,
            metrics=dict(getattr(model, "metrics", {}) or {}),
            metadata={
                "model_metadata": dict(getattr(model, "metadata", {}) or {}),
                **dict(metadata or {}),
            },
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MLModelManifest":
        return cls(
            model_id=str(data["model_id"]),
            model_type=str(data["model_type"]),
            model_artifact=str(data["model_artifact"]),
            feature_schema_version=str(data["feature_schema_version"]),
            feature_names=[str(name) for name in data["feature_names"]],
            feature_schema_hash=str(data["feature_schema_hash"]),
            created_at=normalize_timestamp(data["created_at"]),
            manifest_version=str(data.get("manifest_version", MODEL_MANIFEST_VERSION)),
            stage=str(data.get("stage", "candidate")),
            metrics=dict(data.get("metrics") or {}),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "model_id": self.model_id,
            "model_type": self.model_type,
            "model_artifact": self.model_artifact,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": list(self.feature_names),
            "feature_schema_hash": self.feature_schema_hash,
            "stage": self.stage,
            "metrics": dict(self.metrics),
            "metadata": dict(self.metadata),
            "created_at": _timestamp_text(self.created_at),
        }


@dataclass(frozen=True)
class ForwardReturnLabel:
    """Forward-return label for one symbol/timestamp."""

    symbol: str
    timestamp: datetime
    label_end_timestamp: datetime
    current_close: float
    future_close: float
    target_return: float
    label: int
    horizon_bars: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "label_end_timestamp", normalize_timestamp(self.label_end_timestamp))
        if self.horizon_bars <= 0:
            raise ValueError("horizon_bars must be positive")
        if self.label not in {-1, 0, 1}:
            raise ValueError("label must be -1, 0, or 1")

    @property
    def label_name(self) -> str:
        if self.label > 0:
            return "UP"
        if self.label < 0:
            return "DOWN"
        return "HOLD"


@dataclass(frozen=True)
class MLSample:
    """One row of an ML dataset."""

    symbol: str
    timestamp: datetime
    label_end_timestamp: datetime
    features: dict[str, float]
    label: int
    target_return: float
    horizon_bars: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", normalize_symbol(self.symbol))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "label_end_timestamp", normalize_timestamp(self.label_end_timestamp))
        if not self.features:
            raise ValueError("features must be non-empty")
        if self.label not in {-1, 0, 1}:
            raise ValueError("label must be -1, 0, or 1")

    @property
    def label_name(self) -> str:
        if self.label > 0:
            return "UP"
        if self.label < 0:
            return "DOWN"
        return "HOLD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": _timestamp_text(self.timestamp),
            "label_end_timestamp": _timestamp_text(self.label_end_timestamp),
            "features": dict(self.features),
            "label": self.label,
            "label_name": self.label_name,
            "target_return": self.target_return,
            "horizon_bars": self.horizon_bars,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DatasetSplit:
    """Chronological train/validation/test split."""

    train: list[MLSample]
    validation: list[MLSample]
    test: list[MLSample]
    metadata: dict[str, Any] = field(default_factory=dict)


def _timestamp_text(value: datetime) -> str:
    return normalize_timestamp(value).isoformat().replace("+00:00", "Z")


def build_feature_schema_hash(feature_schema_version: str, feature_names: list[str]) -> str:
    """Return a stable hash for the model's feature schema contract."""
    payload = {
        "schema_version": str(feature_schema_version),
        "feature_names": [str(name) for name in feature_names],
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "DatasetSplit",
    "ForwardReturnLabel",
    "MLModelManifest",
    "MLSample",
    "MLWorkflowError",
    "build_feature_schema_hash",
]
