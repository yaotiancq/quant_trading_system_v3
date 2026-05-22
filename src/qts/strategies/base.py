"""Broker-agnostic strategy interfaces and helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from qts.core import StrategyError
from qts.domain import Bar, FeatureFrame, FeatureRecord, Fill, PortfolioSnapshot, StrategyConfig


StrategyOutput = list[Any]


class Strategy(Protocol):
    """Strategy contract from `INTERFACES.md`."""

    @property
    def name(self) -> str:
        """Stable strategy name."""

    @property
    def symbols(self) -> list[str]:
        """Strategy universe."""

    def initialize(self, strategy_config: StrategyConfig, data_portal: Any, context: Any = None) -> None:
        """Initialize strategy state."""

    def on_data(
        self,
        market_event: Bar,
        features: FeatureRecord | FeatureFrame | Mapping[str, Any] | None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> StrategyOutput:
        """Generate normalized strategy output."""

    def on_fill(self, fill: Fill) -> None:
        """Handle fill updates if needed."""

    def on_end(self, final_context: Any = None) -> None:
        """Finalize strategy state."""


class BaseStrategy:
    """Shared strategy initialization and validation."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config
        self.data_portal: Any = None
        self.context: Any = None
        self._initialized = False
        if config is not None:
            self._initialized = True

    @property
    def name(self) -> str:
        self._require_config()
        return self.config.strategy_id  # type: ignore[union-attr]

    @property
    def symbols(self) -> list[str]:
        self._require_config()
        return list(self.config.symbols)  # type: ignore[union-attr]

    @property
    def parameters(self) -> dict[str, Any]:
        self._require_config()
        return dict(self.config.parameters)  # type: ignore[union-attr]

    def initialize(self, strategy_config: StrategyConfig, data_portal: Any, context: Any = None) -> None:
        self.config = strategy_config
        self.data_portal = data_portal
        self.context = context
        self._initialized = True

    def on_fill(self, fill: Fill) -> None:
        return None

    def on_end(self, final_context: Any = None) -> None:
        return None

    def _require_config(self) -> None:
        if self.config is None or not self._initialized:
            raise StrategyError("strategy must be initialized before use")

    def _validate_symbol(self, symbol: str) -> None:
        self._require_config()
        if symbol not in self.symbols:
            raise StrategyError(f"unsupported symbol for strategy {self.name}: {symbol}")


def feature_value(
    features: FeatureRecord | FeatureFrame | Mapping[str, Any] | None,
    name: str,
    *,
    symbol: str | None = None,
) -> float | None:
    """Extract a feature value from supported Phase 2 feature containers."""
    if features is None:
        return None
    if isinstance(features, FeatureRecord):
        value = features.values.get(name)
        return None if value is None else float(value)
    if isinstance(features, FeatureFrame):
        rows = list(features.features)
        if symbol is not None:
            rows = [row for row in rows if row.get("symbol") == symbol]
        if not rows:
            return None
        value = rows[-1].get(name)
        return None if value is None else float(value)
    if isinstance(features, Mapping):
        values = features.get("values")
        if isinstance(values, Mapping) and name in values:
            value = values[name]
        else:
            value = features.get(name)
        return None if value is None else float(value)
    raise StrategyError(f"unsupported feature container: {type(features).__name__}")


def latest_feature_row(
    features: FeatureRecord | FeatureFrame | Mapping[str, Any] | None,
    *,
    symbol: str | None = None,
) -> Mapping[str, Any] | None:
    if features is None:
        return None
    if isinstance(features, FeatureRecord):
        return features.values
    if isinstance(features, FeatureFrame):
        rows: Sequence[Mapping[str, Any]] = list(features.features)
        if symbol is not None:
            rows = [row for row in rows if row.get("symbol") == symbol]
        return rows[-1] if rows else None
    if isinstance(features, Mapping):
        values = features.get("values")
        return values if isinstance(values, Mapping) else features
    return None


__all__ = ["BaseStrategy", "Strategy", "StrategyOutput", "feature_value", "latest_feature_row"]
