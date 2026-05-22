"""Chronological dataset splitting utilities."""

from __future__ import annotations

from collections.abc import Sequence

from .types import DatasetSplit, MLSample, MLWorkflowError


def chronological_split(
    samples: Sequence[MLSample],
    *,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
    embargo_bars: int = 1,
) -> DatasetSplit:
    """Split samples in timestamp order with optional row embargoes."""
    ordered = _ordered(samples)
    if len(ordered) < 3:
        raise MLWorkflowError("at least three samples are required for train/validation/test split")
    if min(train_fraction, validation_fraction, test_fraction) < 0:
        raise MLWorkflowError("split fractions must be non-negative")
    total_fraction = train_fraction + validation_fraction + test_fraction
    if total_fraction <= 0:
        raise MLWorkflowError("at least one split fraction must be positive")
    if embargo_bars < 0:
        raise MLWorkflowError("embargo_bars must be non-negative")

    normalized_train = train_fraction / total_fraction
    normalized_validation = validation_fraction / total_fraction
    train_end = max(1, int(len(ordered) * normalized_train))
    validation_end = max(train_end + 1, int(len(ordered) * (normalized_train + normalized_validation)))
    validation_end = min(validation_end, len(ordered) - 1)

    validation_start = min(train_end + embargo_bars, validation_end)
    test_start = min(validation_end + embargo_bars, len(ordered))
    train = ordered[:train_end]
    validation = ordered[validation_start:validation_end]
    test = ordered[test_start:]
    if not train or not validation or not test:
        raise MLWorkflowError("split produced an empty train, validation, or test partition")
    return DatasetSplit(
        train=train,
        validation=validation,
        test=test,
        metadata={
            "method": "chronological",
            "train_fraction": train_fraction,
            "validation_fraction": validation_fraction,
            "test_fraction": test_fraction,
            "embargo_bars": embargo_bars,
        },
    )


def walk_forward_splits(
    samples: Sequence[MLSample],
    *,
    train_window: int,
    validation_window: int,
    step: int | None = None,
    embargo_bars: int = 0,
) -> list[DatasetSplit]:
    """Create rolling train/validation windows for walk-forward validation."""
    ordered = _ordered(samples)
    step_size = validation_window if step is None else step
    if train_window <= 0 or validation_window <= 0 or step_size <= 0:
        raise MLWorkflowError("walk-forward windows and step must be positive")
    if embargo_bars < 0:
        raise MLWorkflowError("embargo_bars must be non-negative")

    splits: list[DatasetSplit] = []
    start = 0
    while True:
        train_end = start + train_window
        validation_start = train_end + embargo_bars
        validation_end = validation_start + validation_window
        if validation_end > len(ordered):
            break
        splits.append(
            DatasetSplit(
                train=ordered[start:train_end],
                validation=ordered[validation_start:validation_end],
                test=[],
                metadata={
                    "method": "walk_forward",
                    "train_window": train_window,
                    "validation_window": validation_window,
                    "step": step_size,
                    "embargo_bars": embargo_bars,
                    "start_index": start,
                },
            )
        )
        start += step_size
    if not splits:
        raise MLWorkflowError("walk-forward configuration produced no splits")
    return splits


def _ordered(samples: Sequence[MLSample]) -> list[MLSample]:
    rows = sorted(list(samples), key=lambda sample: (sample.timestamp, sample.symbol))
    if not rows:
        raise MLWorkflowError("cannot split an empty dataset")
    return rows


__all__ = ["chronological_split", "walk_forward_splits"]
