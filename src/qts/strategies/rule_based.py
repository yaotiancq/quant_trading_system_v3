"""Example rule-based strategies."""

from __future__ import annotations

from typing import Any

from qts.core import StrategyError
from qts.domain import (
    Bar,
    FeatureFrame,
    FeatureRecord,
    Fill,
    PortfolioSnapshot,
    Signal,
    SignalDirection,
    StrategyConfig,
)

from .base import BaseStrategy, feature_value


class SMACrossoverStrategy(BaseStrategy):
    """Generate BUY/SELL signals from fast/slow SMA feature crosses."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        super().__init__(config)
        self._previous_relation: dict[str, int] = {}

    def on_data(
        self,
        market_event: Bar,
        features: FeatureRecord | FeatureFrame | dict[str, Any] | None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self._validate_symbol(market_event.symbol)
        fast_window = int(self.parameters.get("fast_window", 20))
        slow_window = int(self.parameters.get("slow_window", 50))
        fast_name = str(self.parameters.get("fast_feature", f"sma_{fast_window}"))
        slow_name = str(self.parameters.get("slow_feature", f"sma_{slow_window}"))
        fast_value = feature_value(features, fast_name, symbol=market_event.symbol)
        slow_value = feature_value(features, slow_name, symbol=market_event.symbol)
        if fast_value is None or slow_value is None:
            return []

        relation = _sign(fast_value - slow_value)
        previous = self._previous_relation.get(market_event.symbol)
        self._previous_relation[market_event.symbol] = relation
        if previous is None or relation == 0:
            return []

        if previous <= 0 < relation:
            direction = SignalDirection.BUY
            reason = "fast_sma_crossed_above_slow_sma"
        elif previous >= 0 > relation:
            direction = SignalDirection.SELL
            reason = "fast_sma_crossed_below_slow_sma"
        else:
            return []

        return [
            Signal(
                signal_id=_signal_id(self.name, market_event, direction),
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=direction,
                strength=min(abs(fast_value - slow_value) / max(abs(slow_value), 1.0), 1.0),
                confidence=1.0,
                reason=reason,
                metadata={
                    "fast_feature": fast_name,
                    "slow_feature": slow_name,
                    "fast_value": fast_value,
                    "slow_value": slow_value,
                },
            )
        ]

    def on_end(self, final_context: Any = None) -> None:
        self._previous_relation.clear()


class RSIMeanReversionStrategy(BaseStrategy):
    """Generate mean-reversion signals from RSI threshold crosses."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        super().__init__(config)
        self._previous_rsi: dict[str, float] = {}

    def on_data(
        self,
        market_event: Bar,
        features: FeatureRecord | FeatureFrame | dict[str, Any] | None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self._validate_symbol(market_event.symbol)
        window = int(self.parameters.get("window", 14))
        oversold = float(self.parameters.get("oversold", 30.0))
        overbought = float(self.parameters.get("overbought", 70.0))
        if oversold >= overbought:
            raise StrategyError("RSI oversold threshold must be below overbought threshold")
        feature_name = str(self.parameters.get("rsi_feature", f"rsi_{window}"))
        current = feature_value(features, feature_name, symbol=market_event.symbol)
        if current is None:
            return []

        previous = self._previous_rsi.get(market_event.symbol)
        self._previous_rsi[market_event.symbol] = current
        if previous is None:
            return []

        if previous > oversold >= current:
            direction = SignalDirection.BUY
            reason = "rsi_crossed_below_oversold"
            strength = min((oversold - current) / max(oversold, 1.0), 1.0)
        elif previous < overbought <= current:
            direction = SignalDirection.SELL
            reason = "rsi_crossed_above_overbought"
            strength = min((current - overbought) / max(100.0 - overbought, 1.0), 1.0)
        else:
            return []

        return [
            Signal(
                signal_id=_signal_id(self.name, market_event, direction),
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=direction,
                strength=strength,
                confidence=1.0,
                reason=reason,
                metadata={
                    "rsi_feature": feature_name,
                    "rsi_value": current,
                    "previous_rsi": previous,
                    "oversold": oversold,
                    "overbought": overbought,
                },
            )
        ]

    def on_end(self, final_context: Any = None) -> None:
        self._previous_rsi.clear()


def create_strategy(config: StrategyConfig) -> BaseStrategy:
    strategy_type = config.strategy_type.lower()
    if strategy_type in {"sma_crossover", "sma_cross"}:
        return SMACrossoverStrategy(config)
    if strategy_type in {"rsi_mean_reversion", "rsi_reversion"}:
        return RSIMeanReversionStrategy(config)
    raise StrategyError(f"unsupported strategy type: {config.strategy_type}")


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _signal_id(strategy_id: str, bar: Bar, direction: SignalDirection) -> str:
    timestamp = bar.timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"{strategy_id}-{bar.symbol}-{timestamp}-{direction.value.lower()}"


__all__ = ["RSIMeanReversionStrategy", "SMACrossoverStrategy", "create_strategy"]
