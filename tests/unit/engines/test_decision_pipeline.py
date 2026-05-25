from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from qts.domain import (
    Bar,
    BarTimeframe,
    BrokerConfig,
    FeatureRecord,
    PortfolioSnapshot,
    Quote,
    RiskConfig,
    RiskDecision,
    RiskDecisionStatus,
    RuntimeConfig,
    RuntimeMode,
    Signal,
    SignalDirection,
    StrategyConfig,
)
from qts.engines import RuntimeDecisionPipeline
from qts.features import FeaturePipeline, FeatureSpec
from qts.portfolio import DefaultPortfolio
from qts.risk import RiskEngine, trade_intent_from_signal
from qts.strategies import BaseStrategy


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


class RecordingDataPortal:
    def __init__(self) -> None:
        self.events: list[Bar | Quote] = []

    def advance(self, event: Bar | Quote) -> None:
        self.events.append(event)


class RecordingStrategy(BaseStrategy):
    def __init__(
        self,
        config: StrategyConfig,
        *,
        direction: SignalDirection = SignalDirection.BUY,
    ) -> None:
        super().__init__(config)
        self.direction = direction
        self.calls: list[dict[str, Any]] = []

    def on_data(
        self,
        market_event: Bar,
        features: FeatureRecord,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self.calls.append(
            {
                "market_event": market_event,
                "features": features,
                "portfolio_snapshot": portfolio_snapshot,
            }
        )
        return [
            Signal(
                signal_id=f"sig-{market_event.symbol}-{len(self.calls)}",
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=self.direction,
                reason="unit_test",
            )
        ]


class CapturingRiskEngine:
    def __init__(self) -> None:
        self.contexts: list[dict[str, Any]] = []

    def evaluate(
        self,
        request: Signal,
        portfolio_snapshot: PortfolioSnapshot,
        market_context: dict[str, Any],
    ) -> RiskDecision:
        self.contexts.append(dict(market_context))
        intent = trade_intent_from_signal(request)
        return RiskDecision(
            decision_id=f"risk-{request.signal_id}",
            timestamp=market_context["timestamp"],
            status=RiskDecisionStatus.APPROVED,
            original_intent=intent,
            approved_intent=intent,
        )


class FixedSessionService:
    def __init__(self) -> None:
        self.timestamps: list[datetime] = []

    def is_tradable(self, timestamp: datetime | str) -> bool:
        if isinstance(timestamp, datetime):
            self.timestamps.append(timestamp)
        return True


def runtime_config(*, blocked_symbols: list[str] | None = None) -> RuntimeConfig:
    return RuntimeConfig(
        run_id="decision-pipeline-unit",
        runtime_mode=RuntimeMode.PAPER,
        symbols=["SPY"],
        timeframe=BarTimeframe.MINUTE,
        market_data={"provider": "external_events"},
        broker=BrokerConfig(broker_type="alpaca_paper", paper=True),
        strategies=[strategy_config()],
        risk=RiskConfig(
            sizing_method="fixed_quantity",
            sizing_parameters={"quantity": 1},
            blocked_symbols=blocked_symbols,
        ),
        portfolio={"starting_cash": 10000},
        execution={"allow_fractional": False},
    )


def strategy_config(symbols: list[str] | None = None) -> StrategyConfig:
    return StrategyConfig(
        strategy_id="strategy-1",
        strategy_type="unit_test",
        symbols=symbols or ["SPY"],
    )


def make_pipeline(
    *,
    strategy: RecordingStrategy | None = None,
    risk_engine: Any | None = None,
    session_service: FixedSessionService | None = None,
    latest_prices: dict[str, float] | None = None,
    blocked_symbols: list[str] | None = None,
) -> tuple[RuntimeDecisionPipeline, RecordingDataPortal, RecordingStrategy]:
    config = runtime_config(blocked_symbols=blocked_symbols)
    portal = RecordingDataPortal()
    strategy = strategy or RecordingStrategy(config.strategies[0])
    strategy.initialize(strategy.config, portal)
    pipeline = RuntimeDecisionPipeline(
        runtime_config=config,
        data_portal=portal,
        portfolio=DefaultPortfolio(10000, timestamp=NOW),
        feature_pipeline=FeaturePipeline(
            [FeatureSpec("sma", {"window": 1})],
            schema_version="features_unit",
        ),
        risk_engine=risk_engine or RiskEngine(config.risk),
        strategies=[strategy],
        session_service=session_service,
        latest_prices=latest_prices,
    )
    return pipeline, portal, strategy


def bar(
    *,
    symbol: str = "SPY",
    timestamp: datetime = NOW,
    close: float = 100,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        timeframe=BarTimeframe.MINUTE,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
    )


def quote(symbol: str = "SPY") -> Quote:
    return Quote(
        symbol=symbol,
        timestamp=NOW,
        bid_price=100,
        ask_price=100.2,
    )


class RuntimeDecisionPipelineTests(unittest.TestCase):
    def test_bar_updates_features_strategy_risk_and_returns_accepted_decisions(self) -> None:
        pipeline, portal, strategy = make_pipeline()

        result = pipeline.on_market_event(bar())

        self.assertEqual(portal.events, [result.market_event])
        self.assertEqual(len(strategy.calls), 1)
        self.assertIsInstance(result.features, FeatureRecord)
        self.assertEqual(len(result.strategy_outputs), 1)
        self.assertEqual(len(result.risk_decisions), 1)
        self.assertEqual(len(result.accepted_decisions), 1)
        self.assertEqual(result.rejected_decisions, [])
        self.assertEqual(result.latest_prices["SPY"], 100)

    def test_quote_updates_price_state_without_strategy_evaluation(self) -> None:
        pipeline, portal, strategy = make_pipeline()

        result = pipeline.on_market_event(quote())

        self.assertEqual(portal.events, [result.market_event])
        self.assertEqual(strategy.calls, [])
        self.assertIsNone(result.features)
        self.assertEqual(result.risk_decisions, [])
        self.assertEqual(result.latest_prices["SPY"], 100.1)

    def test_strategy_for_different_symbol_is_ignored(self) -> None:
        other_strategy = RecordingStrategy(strategy_config(["AAPL"]))
        pipeline, _, strategy = make_pipeline(strategy=other_strategy)

        result = pipeline.on_market_event(bar(symbol="SPY"))

        self.assertIs(strategy, other_strategy)
        self.assertEqual(strategy.calls, [])
        self.assertEqual(result.strategy_outputs, [])
        self.assertEqual(result.risk_decisions, [])

    def test_rejected_risk_decisions_are_returned_separately(self) -> None:
        pipeline, _, _ = make_pipeline(blocked_symbols=["SPY"])

        result = pipeline.on_market_event(bar())

        self.assertEqual(result.accepted_decisions, [])
        self.assertEqual(len(result.rejected_decisions), 1)
        self.assertEqual(result.rejected_decisions[0].status, RiskDecisionStatus.REJECTED)

    def test_risk_context_includes_required_fields(self) -> None:
        risk_engine = CapturingRiskEngine()
        session_service = FixedSessionService()
        pipeline, _, _ = make_pipeline(
            risk_engine=risk_engine,
            session_service=session_service,
        )

        result = pipeline.on_market_event(bar(close=123))
        context = risk_engine.contexts[0]

        self.assertEqual(context["timestamp"], NOW)
        self.assertEqual(context["price"], 123)
        self.assertEqual(context["prices"], {"SPY": 123})
        self.assertIs(context["market_session_service"], session_service)
        self.assertIs(context["bar"], result.market_event)
        self.assertIs(context["current_bar"], result.market_event)
        self.assertEqual(result.risk_context, context)

    def test_latest_price_state_is_preserved_across_events(self) -> None:
        latest_prices = {"AAPL": 199.0}
        pipeline, _, _ = make_pipeline(latest_prices=latest_prices)

        first = pipeline.on_market_event(bar(symbol="SPY", close=100))
        second = pipeline.on_market_event(quote("AAPL"))

        self.assertEqual(first.latest_prices, {"AAPL": 199.0, "SPY": 100})
        self.assertEqual(second.latest_prices, {"AAPL": 100.1, "SPY": 100})
        self.assertEqual(latest_prices, {"AAPL": 100.1, "SPY": 100})


if __name__ == "__main__":
    unittest.main()
