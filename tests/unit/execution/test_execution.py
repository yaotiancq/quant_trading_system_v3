from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.core import ExecutionError
from qts.brokers.backtest import BacktestBrokerage
from qts.domain import (
    Bar,
    BarTimeframe,
    OrderSide,
    OrderStatus,
    RiskDecision,
    RiskDecisionStatus,
    TradeIntent,
)
from qts.execution import ExecutionEngine, OrderManager, OrderRouter, build_order_request


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def make_intent(quantity: float = 10.0) -> TradeIntent:
    return TradeIntent(
        intent_id="intent-1",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=NOW,
        side=OrderSide.BUY,
        quantity=quantity,
        reason="unit_test",
    )


def approved_decision(quantity: float = 10.0) -> RiskDecision:
    intent = make_intent(quantity)
    return RiskDecision(
        decision_id="risk-1",
        timestamp=NOW,
        status=RiskDecisionStatus.APPROVED,
        original_intent=intent,
        approved_intent=intent,
    )


def rejected_decision() -> RiskDecision:
    intent = make_intent()
    return RiskDecision(
        decision_id="risk-rejected",
        timestamp=NOW,
        status=RiskDecisionStatus.REJECTED,
        original_intent=intent,
        reasons=["blocked"],
    )


def bar(minutes: int, open_price: float = 100.0) -> Bar:
    return Bar(
        symbol="SPY",
        timestamp=NOW + timedelta(minutes=minutes),
        timeframe=BarTimeframe.MINUTE,
        open=open_price,
        high=open_price + 1,
        low=open_price - 1,
        close=open_price,
        volume=1000,
    )


class ExecutionTests(unittest.TestCase):
    def test_build_order_request_from_approved_risk_decision(self) -> None:
        request = build_order_request(approved_decision())

        self.assertEqual(request.client_order_id, "coid-risk-1")
        self.assertEqual(request.symbol, "SPY")
        self.assertEqual(request.quantity, 10)
        self.assertEqual(request.metadata["risk_decision_id"], "risk-1")
        self.assertEqual(request.metadata["intent_id"], "intent-1")

    def test_rejected_risk_decision_cannot_build_order_request(self) -> None:
        with self.assertRaises(ExecutionError):
            build_order_request(rejected_decision())

    def test_fractional_quantity_respects_execution_policy(self) -> None:
        request = build_order_request(approved_decision(10.5), allow_fractional=True)

        self.assertEqual(request.quantity, 10.5)

        with self.assertRaises(ExecutionError):
            build_order_request(approved_decision(10.5), allow_fractional=False)

    def test_execution_engine_routes_order_and_tracks_fill(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker))

        order = engine.submit(approved_decision())
        fills = broker.on_market_event(bar(1, open_price=100))
        tracked_order = engine.on_fill(fills[0])

        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        self.assertEqual(tracked_order.status, OrderStatus.FILLED)
        self.assertEqual(tracked_order.filled_quantity, 10)

    def test_execution_engine_uses_allow_fractional_policy(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker), allow_fractional=False)

        with self.assertRaises(ExecutionError):
            engine.submit(approved_decision(1.5))

    def test_order_manager_tracks_open_orders_and_cancellations(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker), order_manager=OrderManager())

        order = engine.submit(approved_decision())
        self.assertEqual([open_order.order_id for open_order in engine.order_manager.list_open_orders()], [order.order_id])

        canceled = engine.cancel_order(order.order_id)

        self.assertEqual(canceled.status, OrderStatus.CANCELED)
        self.assertEqual(engine.order_manager.list_open_orders(), [])

    def test_poll_fills_does_not_apply_duplicate_broker_fill_events(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker))
        order = engine.submit(approved_decision())
        broker.on_market_event(bar(1, open_price=100))

        engine.poll_fills()
        engine.poll_fills()
        tracked_order = engine.order_manager.get_order(order.order_id)

        self.assertEqual(tracked_order.filled_quantity, 10)
        self.assertEqual(tracked_order.status, OrderStatus.FILLED)


if __name__ == "__main__":
    unittest.main()
