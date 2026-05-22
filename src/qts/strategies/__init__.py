"""Broker-agnostic strategy interfaces and example rule-based strategies."""

from __future__ import annotations

from .base import BaseStrategy, Strategy, StrategyOutput, feature_value, latest_feature_row
from .rule_based import RSIMeanReversionStrategy, SMACrossoverStrategy, create_strategy

__all__ = [
    "BaseStrategy",
    "RSIMeanReversionStrategy",
    "SMACrossoverStrategy",
    "Strategy",
    "StrategyOutput",
    "create_strategy",
    "feature_value",
    "latest_feature_row",
]
