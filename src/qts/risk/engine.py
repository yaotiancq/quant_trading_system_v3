"""Risk engine implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from qts.core import RiskError
from qts.domain import (
    Fill,
    PortfolioSnapshot,
    RiskConfig,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    TargetPosition,
    TradeIntent,
    normalize_timestamp,
)

from .rules import RiskRule, default_risk_rules
from .sizing import DefaultPositionSizer, PositionSizer, ensure_trade_intent


class RiskEngine:
    """Aggregate sizing and risk rules into one decision."""

    def __init__(
        self,
        risk_config: RiskConfig,
        *,
        rules: Sequence[RiskRule] | None = None,
        position_sizer: PositionSizer | None = None,
    ) -> None:
        self.risk_config = risk_config
        self.rules = list(rules or default_risk_rules())
        self.position_sizer = position_sizer or DefaultPositionSizer()

    def evaluate(
        self,
        request: Signal | TargetPosition | TradeIntent,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping[str, Any] | None = None,
    ) -> RiskDecision:
        context = dict(market_context or {})
        timestamp = normalize_timestamp(context.get("timestamp", _request_timestamp(request)))
        original_intent = ensure_trade_intent(request, portfolio_snapshot=portfolio_snapshot)
        sizing = self.position_sizer.size(
            request,
            portfolio_snapshot=portfolio_snapshot,
            market_context=context,
            risk_config=self.risk_config,
        )
        candidate = sizing.intent
        modified = sizing.modified
        reasons: list[str] = [sizing.reason]
        rule_results: list[dict[str, Any]] = []

        for rule in self.rules:
            result = rule.evaluate(candidate, portfolio_snapshot, context, self.risk_config)
            rule_results.append(result.to_dict())
            reasons.append(result.reason)
            if result.status == RiskDecisionStatus.REJECTED:
                return RiskDecision(
                    decision_id=_decision_id(original_intent, timestamp),
                    timestamp=timestamp,
                    status=RiskDecisionStatus.REJECTED,
                    original_intent=original_intent,
                    reasons=reasons,
                    rule_results=rule_results,
                    sizing_details=sizing.details,
                )
            if result.status == RiskDecisionStatus.MODIFIED:
                if result.intent is None:
                    raise RiskError(f"risk rule {result.rule_name} returned MODIFIED without intent")
                candidate = result.intent
                modified = True

        return RiskDecision(
            decision_id=_decision_id(original_intent, timestamp),
            timestamp=timestamp,
            status=RiskDecisionStatus.MODIFIED if modified else RiskDecisionStatus.APPROVED,
            original_intent=original_intent,
            approved_intent=candidate,
            reasons=reasons,
            rule_results=rule_results,
            sizing_details=sizing.details,
        )

    def evaluate_many(
        self,
        requests: Sequence[Signal | TargetPosition | TradeIntent],
        portfolio_snapshot: PortfolioSnapshot,
        market_context: Mapping[str, Any] | None = None,
    ) -> list[RiskDecision]:
        return [self.evaluate(request, portfolio_snapshot, market_context) for request in requests]

    def reset_daily_state(self, trading_date: date) -> None:
        for rule in self.rules:
            reset = getattr(rule, "reset_daily_state", None)
            if callable(reset):
                reset()

    def update_after_fill(self, fill: Fill, portfolio_snapshot: PortfolioSnapshot) -> None:
        for rule in self.rules:
            record_fill = getattr(rule, "record_fill", None)
            if callable(record_fill):
                record_fill(fill)


def _request_timestamp(request: Signal | TargetPosition | TradeIntent) -> datetime:
    return request.timestamp


def _decision_id(intent: TradeIntent, timestamp: datetime) -> str:
    return f"risk-{intent.intent_id}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"


__all__ = ["RiskEngine"]
