"""Small dependency-free ML model implementations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qts.domain import FeatureRecord, ModelPrediction, normalize_timestamp

from .types import MLSample, MLWorkflowError


@dataclass(frozen=True)
class DirectionalModel:
    """A simple linear directional classifier for Phase 7 baseline training."""

    model_id: str
    feature_names: list[str]
    feature_schema_version: str
    weights: dict[str, float]
    feature_means: dict[str, float]
    intercept: float = 0.0
    decision_threshold: float = 0.55
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def predict_record(self, record: FeatureRecord) -> ModelPrediction:
        """Predict one feature record."""
        if record.schema_version != self.feature_schema_version:
            raise MLWorkflowError(
                "feature schema mismatch: "
                f"model expects {self.feature_schema_version}, got {record.schema_version}"
            )
        values = _values_for_features(record.values, self.feature_names)
        score = self.score(values)
        probability = _sigmoid(score)
        if probability >= self.decision_threshold:
            label = "UP"
        elif probability <= 1.0 - self.decision_threshold:
            label = "DOWN"
        else:
            label = "HOLD"
        timestamp_text = record.timestamp.strftime("%Y%m%dT%H%M%SZ")
        return ModelPrediction(
            prediction_id=f"pred-{self.model_id}-{record.symbol}-{timestamp_text}",
            model_id=self.model_id,
            symbol=record.symbol,
            timestamp=record.timestamp,
            prediction_value=score,
            prediction_label=label,
            probability=probability,
            horizon=str(self.metadata.get("horizon", "")) or None,
            feature_schema_version=self.feature_schema_version,
            metadata={
                "decision_threshold": self.decision_threshold,
                "feature_names": list(self.feature_names),
            },
        )

    def score(self, values: dict[str, float]) -> float:
        total = self.intercept
        for name in self.feature_names:
            centered = values[name] - self.feature_means.get(name, 0.0)
            total += self.weights.get(name, 0.0) * centered
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": "directional_linear_v1",
            "model_id": self.model_id,
            "feature_names": list(self.feature_names),
            "feature_schema_version": self.feature_schema_version,
            "weights": dict(self.weights),
            "feature_means": dict(self.feature_means),
            "intercept": self.intercept,
            "decision_threshold": self.decision_threshold,
            "metadata": dict(self.metadata),
            "metrics": dict(self.metrics),
            "trained_at": normalize_timestamp(self.trained_at).isoformat().replace("+00:00", "Z"),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectionalModel":
        return cls(
            model_id=str(data["model_id"]),
            feature_names=[str(name) for name in data["feature_names"]],
            feature_schema_version=str(data["feature_schema_version"]),
            weights={str(key): float(value) for key, value in dict(data["weights"]).items()},
            feature_means={
                str(key): float(value) for key, value in dict(data["feature_means"]).items()
            },
            intercept=float(data.get("intercept", 0.0)),
            decision_threshold=float(data.get("decision_threshold", 0.55)),
            metadata=dict(data.get("metadata") or {}),
            metrics=dict(data.get("metrics") or {}),
            trained_at=normalize_timestamp(data.get("trained_at") or datetime.now(timezone.utc)),
        )


def train_directional_model(
    samples: list[MLSample],
    *,
    model_id: str,
    feature_names: list[str],
    feature_schema_version: str,
    decision_threshold: float = 0.55,
    metadata: dict[str, Any] | None = None,
) -> DirectionalModel:
    """Train a small linear classifier from labeled feature means."""
    if not samples:
        raise MLWorkflowError("cannot train model without samples")
    if not feature_names:
        raise MLWorkflowError("feature_names must be non-empty")
    if not 0.5 < decision_threshold < 1.0:
        raise MLWorkflowError("decision_threshold must be between 0.5 and 1.0")

    directional_samples = [sample for sample in samples if sample.label != 0]
    if not directional_samples:
        raise MLWorkflowError("cannot train directional model from HOLD-only samples")

    feature_means = {
        name: _mean([sample.features[name] for sample in directional_samples])
        for name in feature_names
    }
    feature_stdevs = {
        name: _stdev([sample.features[name] for sample in directional_samples], feature_means[name])
        for name in feature_names
    }
    up_samples = [sample for sample in directional_samples if sample.label > 0]
    down_samples = [sample for sample in directional_samples if sample.label < 0]
    weights: dict[str, float] = {}
    for name in feature_names:
        if up_samples and down_samples:
            up_mean = _mean([sample.features[name] for sample in up_samples])
            down_mean = _mean([sample.features[name] for sample in down_samples])
            weights[name] = (up_mean - down_mean) / max(feature_stdevs[name], 1e-12)
        else:
            weights[name] = 0.0

    up_count = len(up_samples)
    down_count = len(down_samples)
    prior = (up_count + 0.5) / (up_count + down_count + 1.0)
    intercept = math.log(prior / (1.0 - prior))
    model = DirectionalModel(
        model_id=model_id,
        feature_names=list(feature_names),
        feature_schema_version=feature_schema_version,
        weights=weights,
        feature_means=feature_means,
        intercept=intercept,
        decision_threshold=decision_threshold,
        metadata=dict(metadata or {}),
    )
    metrics = evaluate_directional_model(model, samples)
    return DirectionalModel(
        model_id=model.model_id,
        feature_names=model.feature_names,
        feature_schema_version=model.feature_schema_version,
        weights=model.weights,
        feature_means=model.feature_means,
        intercept=model.intercept,
        decision_threshold=model.decision_threshold,
        metadata=model.metadata,
        metrics={"training": metrics},
        trained_at=model.trained_at,
    )


def evaluate_directional_model(model: DirectionalModel, samples: list[MLSample]) -> dict[str, Any]:
    """Evaluate directional accuracy for a model."""
    if not samples:
        return {
            "sample_count": 0,
            "accuracy": None,
            "directional_accuracy": None,
            "confusion": {},
        }

    correct = 0
    directional_total = 0
    directional_correct = 0
    confusion: dict[str, dict[str, int]] = {}
    for sample in samples:
        record = FeatureRecord(
            symbol=sample.symbol,
            timestamp=sample.timestamp,
            values=dict(sample.features),
            schema_version=model.feature_schema_version,
        )
        prediction = model.predict_record(record)
        actual = sample.label_name
        predicted = str(prediction.prediction_label)
        confusion.setdefault(actual, {})
        confusion[actual][predicted] = confusion[actual].get(predicted, 0) + 1
        if predicted == actual:
            correct += 1
        if actual != "HOLD":
            directional_total += 1
            if predicted == actual:
                directional_correct += 1

    return {
        "sample_count": len(samples),
        "accuracy": correct / len(samples),
        "directional_accuracy": (
            directional_correct / directional_total if directional_total else None
        ),
        "confusion": confusion,
    }


def _values_for_features(values: dict[str, Any], feature_names: list[str]) -> dict[str, float]:
    missing = [name for name in feature_names if values.get(name) is None]
    if missing:
        raise MLWorkflowError("missing required model features: " + ", ".join(sorted(missing)))
    return {name: float(values[name]) for name in feature_names}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 1.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance) or 1.0


def _sigmoid(value: float) -> float:
    bounded = max(min(value, 60.0), -60.0)
    return 1.0 / (1.0 + math.exp(-bounded))


__all__ = ["DirectionalModel", "evaluate_directional_model", "train_directional_model"]
