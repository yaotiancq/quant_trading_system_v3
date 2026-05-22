"""Position sizing policies."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from qts.core import RiskError
from qts.domain import (
    OrderSide,
    OrderType,
    PortfolioSnapshot,
    RiskConfig,
    Signal,
    SignalDirection,
    TargetPosition,
    TimeInForce,
    TradeIntent,
)

from .types import SizingResult


class PositionSizer(Protocol):
    """Position sizing contract."""

    def size(
        self,
        request: Signal | TargetPosition | TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: dict,
        risk_config: RiskConfig,
    ) -> SizingResult:
        """Return a sized trade intent."""


class DefaultPositionSizer:
    """Built-in sizing policies for Phase 3."""

    def size(
        self,
        request: Signal | TargetPosition | TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: dict,
        risk_config: RiskConfig,
    ) -> SizingResult:
        intent = ensure_trade_intent(request, portfolio_snapshot=portfolio_snapshot)
        if intent.quantity is not None or intent.notional is not None:
            return SizingResult(
                intent=intent,
                modified=False,
                reason="already_sized",
                details={"sizing_method": "preserve_existing"},
            )

        method = risk_config.sizing_method.lower()
        params = dict(risk_config.sizing_parameters)
        if method == "fixed_quantity":
            quantity = float(params.get("quantity", params.get("quantity_per_trade", 0)))
            if quantity <= 0:
                raise RiskError("fixed_quantity sizing requires positive quantity")
            sized = replace(intent, quantity=quantity)
            details = {"sizing_method": method, "quantity": quantity}
        elif method in {"fixed_notional", "fixed_dollar"}:
            notional = float(params.get("notional_per_trade", params.get("notional", 0)))
            if notional <= 0:
                raise RiskError("fixed_notional sizing requires positive notional_per_trade")
            sized = replace(intent, notional=notional)
            details = {"sizing_method": method, "notional": notional}
        elif method in {"percent_equity", "percent_of_equity"}:
            percent = float(params.get("percent", params.get("percent_of_equity", 0)))
            if percent <= 0:
                raise RiskError("percent_equity sizing requires positive percent")
            notional = portfolio_snapshot.equity * percent
            if notional <= 0:
                raise RiskError("percent_equity sizing produced non-positive notional")
            sized = replace(intent, notional=notional)
            details = {"sizing_method": method, "percent": percent, "notional": notional}
        else:
            raise RiskError(f"unsupported sizing method: {risk_config.sizing_method}")

        return SizingResult(
            intent=sized,
            modified=True,
            reason="sizing_applied",
            details=details,
        )


def ensure_trade_intent(
    request: Signal | TargetPosition | TradeIntent,
    *,
    portfolio_snapshot: PortfolioSnapshot,
) -> TradeIntent:
    if isinstance(request, TradeIntent):
        return request
    if isinstance(request, Signal):
        return trade_intent_from_signal(request)
    if isinstance(request, TargetPosition):
        return trade_intent_from_target_position(request, portfolio_snapshot)
    raise RiskError(f"unsupported risk input: {type(request).__name__}")


def trade_intent_from_signal(signal: Signal) -> TradeIntent:
    if signal.direction in {SignalDirection.BUY, SignalDirection.COVER}:
        side = OrderSide.BUY
    elif signal.direction in {SignalDirection.SELL, SignalDirection.SHORT, SignalDirection.EXIT}:
        side = OrderSide.SELL
    else:
        raise RiskError("HOLD signals cannot be converted to trade intents")

    return TradeIntent(
        intent_id=f"intent-{signal.signal_id}",
        strategy_id=signal.strategy_id,
        symbol=signal.symbol,
        timestamp=signal.timestamp,
        side=side,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        source_signal_id=signal.signal_id,
        reason=signal.reason,
        metadata={"source": "signal", **signal.metadata},
    )


def trade_intent_from_target_position(
    target: TargetPosition,
    portfolio_snapshot: PortfolioSnapshot,
) -> TradeIntent:
    if target.target_quantity is not None:
        current_quantity = _current_quantity(target.symbol, portfolio_snapshot)
        delta = target.target_quantity - current_quantity
        if delta == 0:
            raise RiskError("target position already satisfied")
        return TradeIntent(
            intent_id=f"intent-{target.target_id}",
            strategy_id=target.strategy_id,
            symbol=target.symbol,
            timestamp=target.timestamp,
            side=OrderSide.BUY if delta > 0 else OrderSide.SELL,
            quantity=abs(delta),
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            reason=target.reason,
            metadata={"source": "target_position", **target.metadata},
        )
    if target.target_notional is not None:
        return TradeIntent(
            intent_id=f"intent-{target.target_id}",
            strategy_id=target.strategy_id,
            symbol=target.symbol,
            timestamp=target.timestamp,
            side=OrderSide.BUY,
            notional=target.target_notional,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            reason=target.reason,
            metadata={"source": "target_position", **target.metadata},
        )
    if target.target_weight is not None:
        notional = abs(portfolio_snapshot.equity * target.target_weight)
        if notional <= 0:
            raise RiskError("target_weight produced non-positive notional")
        return TradeIntent(
            intent_id=f"intent-{target.target_id}",
            strategy_id=target.strategy_id,
            symbol=target.symbol,
            timestamp=target.timestamp,
            side=OrderSide.BUY if target.target_weight >= 0 else OrderSide.SELL,
            notional=notional,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            reason=target.reason,
            metadata={"source": "target_position", **target.metadata},
        )
    raise RiskError("target position has no actionable target")


def _current_quantity(symbol: str, portfolio_snapshot: PortfolioSnapshot) -> float:
    for position in portfolio_snapshot.positions:
        if position.symbol == symbol:
            return position.quantity
    return 0.0


__all__ = [
    "DefaultPositionSizer",
    "PositionSizer",
    "ensure_trade_intent",
    "trade_intent_from_signal",
    "trade_intent_from_target_position",
]
