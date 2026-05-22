"""Shared ML workflow types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from qts.domain import normalize_symbol, normalize_timestamp


class MLWorkflowError(Exception):
    """Raised for controlled ML workflow failures."""


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


__all__ = [
    "DatasetSplit",
    "ForwardReturnLabel",
    "MLSample",
    "MLWorkflowError",
]
