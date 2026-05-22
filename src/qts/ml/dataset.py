"""Dataset construction from normalized bars and reusable features."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qts.domain import Bar, normalize_symbol
from qts.features import FeaturePipeline

from .labels import build_forward_return_labels
from .types import MLSample, MLWorkflowError


@dataclass(frozen=True)
class MLDataset:
    """Row-oriented ML dataset."""

    samples: list[MLSample]
    feature_names: list[str]
    feature_schema_version: str
    label_config: dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("MLDataset requires at least one sample")
        if not self.feature_names:
            raise ValueError("feature_names must be non-empty")

    @property
    def symbols(self) -> list[str]:
        return sorted({sample.symbol for sample in self.samples})

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": self.symbols,
            "feature_names": list(self.feature_names),
            "feature_schema_version": self.feature_schema_version,
            "label_config": dict(self.label_config),
            "generated_at": self.generated_at.isoformat().replace("+00:00", "Z"),
            "samples": [sample.to_dict() for sample in self.samples],
        }


def build_ml_dataset(
    bars: Sequence[Bar],
    *,
    feature_pipeline: FeaturePipeline,
    horizon_bars: int = 1,
    up_threshold: float = 0.0,
    down_threshold: float = 0.0,
    drop_missing_features: bool = True,
    include_hold_labels: bool = True,
) -> MLDataset:
    """Build labeled feature samples for offline training."""
    if not bars:
        raise MLWorkflowError("cannot build ML dataset from empty bars")
    labels = build_forward_return_labels(
        bars,
        horizon_bars=horizon_bars,
        up_threshold=up_threshold,
        down_threshold=down_threshold,
    )
    frame = feature_pipeline.transform_batch(bars)
    schema = feature_pipeline.get_schema()
    feature_names = list(schema.feature_names)

    samples: list[MLSample] = []
    for row in frame.features:
        symbol = normalize_symbol(str(row["symbol"]))
        timestamp = row["timestamp"]
        label = labels.get((symbol, timestamp))
        if label is None:
            continue
        features: dict[str, float] = {}
        missing = False
        for feature_name in feature_names:
            value = row.get(feature_name)
            if value is None:
                missing = True
                break
            features[feature_name] = float(value)
        if missing and drop_missing_features:
            continue
        if label.label == 0 and not include_hold_labels:
            continue
        samples.append(
            MLSample(
                symbol=symbol,
                timestamp=timestamp,
                label_end_timestamp=label.label_end_timestamp,
                features=features,
                label=label.label,
                target_return=label.target_return,
                horizon_bars=horizon_bars,
                metadata={"label_name": label.label_name},
            )
        )

    if not samples:
        raise MLWorkflowError("ML dataset has no samples after filtering")
    return MLDataset(
        samples=sorted(samples, key=lambda sample: (sample.timestamp, sample.symbol)),
        feature_names=feature_names,
        feature_schema_version=frame.schema_version,
        label_config={
            "horizon_bars": horizon_bars,
            "up_threshold": up_threshold,
            "down_threshold": down_threshold,
            "include_hold_labels": include_hold_labels,
            "drop_missing_features": drop_missing_features,
        },
    )


__all__ = ["MLDataset", "build_ml_dataset"]
