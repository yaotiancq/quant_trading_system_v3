"""Basic risk rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, time, timezone
from typing import Protocol

from qts.domain import (
    Fill,
    OrderSide,
    PortfolioSnapshot,
    RiskConfig,
    RiskDecisionStatus,
    TradeIntent,
    normalize_symbol,
    normalize_timestamp,
)

from .types import RuleResult


class RiskRule(Protocol):
    """Risk rule contract."""

    @property
    def name(self) -> str:
        """Stable rule name."""

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        """Evaluate a trade intent."""


class SymbolRestrictionRule:
    @property
    def name(self) -> str:
        return "symbol_restriction"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        if risk_config.allowed_symbols and trade_intent.symbol not in risk_config.allowed_symbols:
            return _reject(self.name, "symbol_not_allowed", {"symbol": trade_intent.symbol})
        if risk_config.blocked_symbols and trade_intent.symbol in risk_config.blocked_symbols:
            return _reject(self.name, "symbol_blocked", {"symbol": trade_intent.symbol})
        return _approve(self.name, "symbol_allowed")


class MaxPositionNotionalRule:
    @property
    def name(self) -> str:
        return "max_position_notional"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        limit = risk_config.max_position_notional
        if limit is None:
            return _approve(self.name, "max_position_notional_not_configured")
        exposure = projected_symbol_exposure(trade_intent, portfolio_snapshot, market_context)
        if exposure is None:
            return _reject(self.name, "notional_unavailable_for_position_limit")
        current, projected = exposure
        if projected <= limit:
            return _approve(
                self.name,
                "within_position_notional_limit",
                {"current": current, "projected": projected},
            )
        if projected <= current:
            return _approve(
                self.name,
                "position_exposure_reduced",
                {"current": current, "projected": projected, "limit": limit},
            )

        price = market_price(trade_intent, market_context)
        if current == 0 and trade_intent.notional is not None:
            modified = replace(trade_intent, notional=limit)
        elif current == 0 and trade_intent.quantity is not None and price:
            modified = replace(trade_intent, quantity=limit / price)
        else:
            return _reject(
                self.name,
                "position_notional_exceeds_limit",
                {"current": current, "projected": projected, "limit": limit},
            )
        return _modify(
            self.name,
            "position_notional_reduced_to_limit",
            modified,
            {"original_notional": projected, "limit": limit},
        )


class MaxGrossExposureRule:
    @property
    def name(self) -> str:
        return "max_gross_exposure"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        limit = risk_config.max_gross_exposure
        if limit is None:
            return _approve(self.name, "max_gross_exposure_not_configured")
        exposure = projected_symbol_exposure(trade_intent, portfolio_snapshot, market_context)
        if exposure is None:
            return _reject(self.name, "notional_unavailable_for_gross_exposure")
        current_symbol_exposure, projected_symbol = exposure
        projected = max(
            0.0,
            portfolio_snapshot.gross_exposure - current_symbol_exposure + projected_symbol,
        )
        if projected > limit:
            if projected <= portfolio_snapshot.gross_exposure:
                return _approve(
                    self.name,
                    "gross_exposure_reduced",
                    {
                        "current": portfolio_snapshot.gross_exposure,
                        "projected": projected,
                        "limit": limit,
                    },
                )
            return _reject(
                self.name,
                "gross_exposure_limit_exceeded",
                {
                    "current": portfolio_snapshot.gross_exposure,
                    "projected": projected,
                    "limit": limit,
                },
            )
        return _approve(self.name, "within_gross_exposure_limit", {"projected": projected})


class BuyingPowerRule:
    @property
    def name(self) -> str:
        return "buying_power"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        if trade_intent.side == OrderSide.SELL:
            return _approve(self.name, "sell_order_does_not_require_buying_power")
        notional = estimate_notional(trade_intent, market_context)
        if notional is None:
            return _reject(self.name, "notional_unavailable_for_buying_power")
        available = float(portfolio_snapshot.metadata.get("buying_power", portfolio_snapshot.cash))
        if notional > available:
            return _reject(
                self.name,
                "insufficient_buying_power",
                {"required": notional, "available": available},
            )
        return _approve(self.name, "buying_power_ok", {"required": notional})


class MaxSymbolWeightRule:
    @property
    def name(self) -> str:
        return "max_symbol_weight"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        limit = risk_config.max_symbol_weight
        if limit is None:
            return _approve(self.name, "max_symbol_weight_not_configured")
        if portfolio_snapshot.equity <= 0:
            return _reject(self.name, "non_positive_equity_for_symbol_weight")
        exposure = projected_symbol_exposure(trade_intent, portfolio_snapshot, market_context)
        if exposure is None:
            return _reject(self.name, "notional_unavailable_for_symbol_weight")
        current, projected = exposure
        weight = projected / portfolio_snapshot.equity
        if weight > limit:
            if projected <= current:
                return _approve(
                    self.name,
                    "symbol_weight_reduced",
                    {"current": current, "projected": projected, "weight": weight, "limit": limit},
                )
            return _reject(
                self.name,
                "symbol_weight_limit_exceeded",
                {"weight": weight, "limit": limit},
            )
        return _approve(self.name, "within_symbol_weight_limit", {"weight": weight})


class TradingSessionRule:
    @property
    def name(self) -> str:
        return "trading_session"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        rules = dict(risk_config.session_rules or {})
        if not rules.get("enabled", False):
            return _approve(self.name, "session_rule_not_enabled")

        timestamp = normalize_timestamp(market_context.get("timestamp", trade_intent.timestamp))
        weekdays = set(rules.get("weekdays", [0, 1, 2, 3, 4]))
        if timestamp.weekday() not in weekdays:
            return _reject(self.name, "outside_trading_weekday", {"weekday": timestamp.weekday()})

        open_time = _parse_hhmm(str(rules.get("market_open", "14:30")))
        close_time = _parse_hhmm(str(rules.get("market_close", "21:00")))
        current_time = timestamp.astimezone(timezone.utc).time().replace(tzinfo=None)
        if current_time < open_time or current_time > close_time:
            return _reject(
                self.name,
                "outside_trading_session",
                {"current_time": current_time.isoformat(timespec="minutes")},
            )
        return _approve(self.name, "inside_trading_session")


class DailyLossLimitRule:
    @property
    def name(self) -> str:
        return "daily_loss_limit"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        limit = risk_config.daily_loss_limit
        if limit is None:
            return _approve(self.name, "daily_loss_limit_not_configured")
        if portfolio_snapshot.realized_pnl <= -abs(limit):
            return _reject(
                self.name,
                "daily_loss_limit_reached",
                {"realized_pnl": portfolio_snapshot.realized_pnl, "limit": limit},
            )
        return _approve(self.name, "daily_loss_limit_ok")


class CooldownRule:
    def __init__(self) -> None:
        self._last_trade_time_by_symbol: dict[str, datetime] = {}

    @property
    def name(self) -> str:
        return "cooldown"

    def evaluate(
        self,
        trade_intent: TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping,
        risk_config: RiskConfig,
    ) -> RuleResult:
        cooldown_seconds = risk_config.cooldown_seconds
        if not cooldown_seconds:
            return _approve(self.name, "cooldown_not_configured")
        last_trade_time = self._last_trade_time_by_symbol.get(trade_intent.symbol)
        if last_trade_time is None:
            return _approve(self.name, "cooldown_no_previous_trade")
        timestamp = normalize_timestamp(market_context.get("timestamp", trade_intent.timestamp))
        elapsed = (timestamp - last_trade_time).total_seconds()
        if elapsed < cooldown_seconds:
            return _reject(
                self.name,
                "cooldown_active",
                {"elapsed_seconds": elapsed, "cooldown_seconds": cooldown_seconds},
            )
        return _approve(self.name, "cooldown_elapsed", {"elapsed_seconds": elapsed})

    def record_fill(self, fill: Fill) -> None:
        self._last_trade_time_by_symbol[fill.symbol] = fill.timestamp

    def reset_daily_state(self) -> None:
        self._last_trade_time_by_symbol.clear()


def default_risk_rules() -> list[RiskRule]:
    return [
        SymbolRestrictionRule(),
        TradingSessionRule(),
        DailyLossLimitRule(),
        CooldownRule(),
        MaxPositionNotionalRule(),
        MaxSymbolWeightRule(),
        MaxGrossExposureRule(),
        BuyingPowerRule(),
    ]


def estimate_notional(trade_intent: TradeIntent, market_context: Mapping) -> float | None:
    if trade_intent.notional is not None:
        return float(trade_intent.notional)
    if trade_intent.quantity is None:
        return None
    price = market_price(trade_intent, market_context)
    if price is None:
        return None
    return abs(float(trade_intent.quantity) * price)


def projected_symbol_exposure(
    trade_intent: TradeIntent,
    portfolio_snapshot: PortfolioSnapshot,
    market_context: Mapping,
) -> tuple[float, float] | None:
    price = market_price(trade_intent, market_context)
    current_exposure = _current_position_exposure(portfolio_snapshot, trade_intent.symbol, price)
    if price is None and trade_intent.notional is not None:
        projected = current_exposure + float(trade_intent.notional)
        return current_exposure, projected
    if price is None:
        return None
    delta_quantity = _intent_delta_quantity(trade_intent, price)
    if delta_quantity is None:
        return None
    current_quantity = _current_position_quantity(portfolio_snapshot, trade_intent.symbol)
    projected_exposure = abs((current_quantity + delta_quantity) * price)
    return current_exposure, projected_exposure


def market_price(trade_intent: TradeIntent, market_context: Mapping) -> float | None:
    for key in ("price", "latest_price"):
        if market_context.get(key) is not None:
            return float(market_context[key])
    prices = market_context.get("prices")
    if isinstance(prices, Mapping):
        value = prices.get(trade_intent.symbol) or prices.get(normalize_symbol(trade_intent.symbol))
        if value is not None:
            return float(value)
    for key in ("bar", "current_bar"):
        bar = market_context.get(key)
        if getattr(bar, "symbol", None) == trade_intent.symbol and getattr(bar, "close", None) is not None:
            return float(bar.close)
    return None


def _intent_delta_quantity(trade_intent: TradeIntent, price: float) -> float | None:
    if trade_intent.quantity is not None:
        quantity = float(trade_intent.quantity)
    elif trade_intent.notional is not None:
        quantity = float(trade_intent.notional) / price
    else:
        return None
    return quantity if trade_intent.side == OrderSide.BUY else -quantity


def _current_position_quantity(
    portfolio_snapshot: PortfolioSnapshot,
    symbol: str,
) -> float:
    wanted_symbol = normalize_symbol(symbol)
    return sum(
        float(position.quantity)
        for position in portfolio_snapshot.positions
        if position.symbol == wanted_symbol
    )


def _current_position_exposure(
    portfolio_snapshot: PortfolioSnapshot,
    symbol: str,
    price: float | None,
) -> float:
    wanted_symbol = normalize_symbol(symbol)
    exposure = 0.0
    for position in portfolio_snapshot.positions:
        if position.symbol != wanted_symbol:
            continue
        if price is not None:
            exposure += abs(float(position.quantity) * price)
        elif position.market_value is not None:
            exposure += float(position.market_value)
        elif position.market_price is not None:
            exposure += abs(float(position.quantity) * position.market_price)
    return exposure


def _approve(name: str, reason: str, details: dict | None = None) -> RuleResult:
    return RuleResult(
        rule_name=name,
        status=RiskDecisionStatus.APPROVED,
        reason=reason,
        details=dict(details or {}),
    )


def _reject(name: str, reason: str, details: dict | None = None) -> RuleResult:
    return RuleResult(
        rule_name=name,
        status=RiskDecisionStatus.REJECTED,
        reason=reason,
        details=dict(details or {}),
    )


def _modify(name: str, reason: str, intent: TradeIntent, details: dict | None = None) -> RuleResult:
    return RuleResult(
        rule_name=name,
        status=RiskDecisionStatus.MODIFIED,
        reason=reason,
        intent=intent,
        details=dict(details or {}),
    )


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(hour=int(hour), minute=int(minute))


__all__ = [
    "BuyingPowerRule",
    "CooldownRule",
    "DailyLossLimitRule",
    "MaxGrossExposureRule",
    "MaxPositionNotionalRule",
    "MaxSymbolWeightRule",
    "RiskRule",
    "SymbolRestrictionRule",
    "TradingSessionRule",
    "default_risk_rules",
    "estimate_notional",
    "market_price",
    "projected_symbol_exposure",
]
