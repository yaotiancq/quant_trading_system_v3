"""Leakage checks for chronological ML splits."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from .types import DatasetSplit, MLSample, MLWorkflowError


def validate_no_temporal_leakage(
    training_samples: Sequence[MLSample],
    evaluation_samples: Sequence[MLSample],
    *,
    embargo: timedelta = timedelta(0),
) -> bool:
    """Ensure training labels do not reach into evaluation feature timestamps."""
    if not training_samples or not evaluation_samples:
        return True
    latest_training_label_end = max(sample.label_end_timestamp for sample in training_samples)
    earliest_evaluation_timestamp = min(sample.timestamp for sample in evaluation_samples)
    if latest_training_label_end + embargo >= earliest_evaluation_timestamp:
        raise MLWorkflowError(
            "temporal leakage detected: training label horizon overlaps evaluation features"
        )
    return True


def validate_split_no_leakage(
    split: DatasetSplit,
    *,
    embargo: timedelta = timedelta(0),
) -> bool:
    """Validate train/validation/test chronological boundaries."""
    validate_no_temporal_leakage(split.train, split.validation, embargo=embargo)
    if split.validation and split.test:
        validate_no_temporal_leakage(split.validation, split.test, embargo=embargo)
    return True


__all__ = ["validate_no_temporal_leakage", "validate_split_no_leakage"]
