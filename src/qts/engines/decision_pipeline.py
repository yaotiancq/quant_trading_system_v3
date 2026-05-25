"""Shared runtime feature, strategy, and risk decision pipeline."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from qts.calendar import MarketSessionService
from qts.domain import (
    Bar,
    FeatureFrame,
    FeatureRecord,
    PortfolioSnapshot,
    Quote,
    RiskDecision,
    RiskDecisionStatus,
    RuntimeConfig,
)
from qts.features import FeaturePipeline
from qts.portfolio import DefaultPortfolio
from qts.risk import RiskEngine
from qts.strategies import BaseStrategy


MarketEvent = Bar | Quote
StrategyOutput = Any
BeforeMarkCallback = Callable[[MarketEvent], None]


@dataclass(frozen=True)
class RuntimeDecisionResult:
    """Result of running one normalized market event through the decision path."""

    market_event: MarketEvent
    portfolio_snapshot: PortfolioSnapshot
    features: FeatureRecord | FeatureFrame | None
    strategy_outputs: list[StrategyOutput]
    risk_decisions: list[RiskDecision]
    accepted_decisions: list[RiskDecision]
    rejected_decisions: list[RiskDecision]
    latest_prices: dict[str, float]
    risk_context: dict[str, Any]


class RuntimeDecisionPipeline:
    """Common market event -> feature -> strategy -> risk transformation.

    The pipeline intentionally stops at risk decisions. Runtime-specific order
    submission, broker synchronization, fills, reconciliation, and live safety
    gates remain owned by the engines.
    """

    def __init__(
        self,
        *,
        runtime_config: RuntimeConfig,
        data_portal: Any,
        portfolio: DefaultPortfolio,
        feature_pipeline: FeaturePipeline,
        risk_engine: RiskEngine,
        strategies: Sequence[BaseStrategy],
        session_service: MarketSessionService | None = None,
        latest_prices: dict[str, float] | None = None,
    ) -> None:
        self.runtime_config = runtime_config
        self.data_portal = data_portal
        self.portfolio = portfolio
        self.feature_pipeline = feature_pipeline
        self.risk_engine = risk_engine
        self.strategies = list(strategies)
        self.session_service = session_service
        self.latest_prices = latest_prices if latest_prices is not None else {}

    def on_market_event(
        self,
        event: MarketEvent,
        *,
        before_mark_to_market: BeforeMarkCallback | None = None,
    ) -> RuntimeDecisionResult:
        """Advance state and return risk decisions for one market event."""
        self.data_portal.advance(event)
        if before_mark_to_market is not None:
            before_mark_to_market(event)

        price = _event_price(event)
        self.latest_prices[event.symbol] = price
        snapshot = self.portfolio.mark_to_market(self.latest_prices, event.timestamp)
        risk_context = self._risk_context(event, price)

        if isinstance(event, Quote):
            return RuntimeDecisionResult(
                market_event=event,
                portfolio_snapshot=snapshot,
                features=None,
                strategy_outputs=[],
                risk_decisions=[],
                accepted_decisions=[],
                rejected_decisions=[],
                latest_prices=dict(self.latest_prices),
                risk_context=risk_context,
            )

        features = self.feature_pipeline.update_online(event)
        outputs: list[StrategyOutput] = []
        decisions: list[RiskDecision] = []
        accepted: list[RiskDecision] = []
        rejected: list[RiskDecision] = []

        for strategy in self.strategies:
            if event.symbol not in strategy.symbols:
                continue
            strategy_outputs = strategy.on_data(event, features, snapshot)
            outputs.extend(strategy_outputs)
            for output in strategy_outputs:
                decision = self.risk_engine.evaluate(output, snapshot, risk_context)
                decisions.append(decision)
                if decision.status == RiskDecisionStatus.REJECTED:
                    rejected.append(decision)
                else:
                    accepted.append(decision)

        return RuntimeDecisionResult(
            market_event=event,
            portfolio_snapshot=snapshot,
            features=features,
            strategy_outputs=outputs,
            risk_decisions=decisions,
            accepted_decisions=accepted,
            rejected_decisions=rejected,
            latest_prices=dict(self.latest_prices),
            risk_context=risk_context,
        )

    def _risk_context(self, event: MarketEvent, price: float) -> dict[str, Any]:
        context: dict[str, Any] = {
            "timestamp": event.timestamp,
            "market_session_service": self.session_service,
            "price": price,
            "prices": dict(self.latest_prices),
        }
        if isinstance(event, Bar):
            context["bar"] = event
            context["current_bar"] = event
        else:
            context["quote"] = event
        return context


def _event_price(event: MarketEvent) -> float:
    if isinstance(event, Quote):
        return (event.bid_price + event.ask_price) / 2.0
    return event.close


__all__ = [
    "BeforeMarkCallback",
    "MarketEvent",
    "RuntimeDecisionPipeline",
    "RuntimeDecisionResult",
]
