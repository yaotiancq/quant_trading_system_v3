from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from qts.core import ExecutionError
from qts.brokers.backtest import BacktestBrokerage
from qts.domain import (
    Bar,
    BarTimeframe,
    BrokerEventType,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskDecisionStatus,
    TimeInForce,
    TradeIntent,
)
from qts.execution import (
    ExecutionEngine,
    InMemoryBrokerEventSource,
    OrderManager,
    OrderRouter,
    broker_event_from_fill,
    broker_event_from_order,
    build_order_request,
)


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


def make_notional_intent(notional: float = 1000.0) -> TradeIntent:
    return TradeIntent(
        intent_id="intent-notional",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=NOW,
        side=OrderSide.BUY,
        notional=notional,
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


def approved_notional_decision(notional: float = 1000.0) -> RiskDecision:
    intent = make_notional_intent(notional)
    return RiskDecision(
        decision_id="risk-notional",
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

    def test_notional_order_requires_fractional_execution_policy(self) -> None:
        request = build_order_request(approved_notional_decision(), allow_fractional=True)

        self.assertEqual(request.notional, 1000)
        self.assertIsNone(request.quantity)

        with self.assertRaisesRegex(ExecutionError, "notional orders require"):
            build_order_request(approved_notional_decision(), allow_fractional=False)

    def test_trade_intent_rejects_quantity_and_notional_together(self) -> None:
        with self.assertRaisesRegex(ValueError, "either quantity or notional"):
            TradeIntent(
                intent_id="invalid-intent",
                strategy_id="strategy-1",
                symbol="SPY",
                timestamp=NOW,
                side=OrderSide.BUY,
                quantity=1,
                notional=100,
            )

    def test_order_request_requires_exactly_one_quantity_or_notional(self) -> None:
        base = {
            "client_order_id": "coid-invalid",
            "strategy_id": "strategy-1",
            "symbol": "SPY",
            "timestamp": NOW,
            "side": OrderSide.BUY,
            "order_type": OrderType.MARKET,
            "time_in_force": TimeInForce.DAY,
        }

        with self.assertRaisesRegex(ValueError, "exactly one"):
            OrderRequest(**base)

        with self.assertRaisesRegex(ValueError, "exactly one"):
            OrderRequest(**base, quantity=1, notional=100)

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

    def test_order_updates_do_not_regress_lifecycle_state(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker))
        order = engine.submit(approved_decision())
        submitted = replace(
            order,
            status=OrderStatus.SUBMITTED,
            updated_at=NOW + timedelta(minutes=1),
        )
        stale = replace(
            order,
            status=OrderStatus.ACCEPTED,
            updated_at=NOW,
        )

        engine.on_order_update(submitted)
        engine.on_order_update(stale)

        tracked_order = engine.order_manager.get_order(order.order_id)
        self.assertEqual(tracked_order.status, OrderStatus.SUBMITTED)
        self.assertEqual(tracked_order.updated_at, NOW + timedelta(minutes=1))

    def test_broker_fill_event_is_idempotent(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker))
        order = engine.submit(approved_decision())
        fill = broker.on_market_event(bar(1, open_price=100))[0]
        event = broker_event_from_fill(fill)

        engine.on_broker_event(event)
        engine.on_broker_event(event)

        tracked_order = engine.order_manager.get_order(order.order_id)
        self.assertEqual(tracked_order.filled_quantity, 10)
        self.assertEqual(tracked_order.status, OrderStatus.FILLED)

    def test_order_router_poll_events_returns_order_updates_and_fills(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        router = OrderRouter(broker)
        engine = ExecutionEngine(router)
        engine.submit(approved_decision())
        broker.on_market_event(bar(1, open_price=100))

        events = router.poll_events()

        self.assertEqual(
            [event.event_type for event in events],
            [BrokerEventType.FILL, BrokerEventType.ORDER_UPDATE],
        )
        self.assertTrue(events[0].event_id.startswith("fill:"))
        self.assertTrue(events[1].event_id.startswith("order:"))

    def test_order_broker_event_update_uses_order_payload(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        engine = ExecutionEngine(OrderRouter(broker))
        order = engine.submit(approved_decision())
        submitted = replace(
            order,
            status=OrderStatus.SUBMITTED,
            updated_at=NOW + timedelta(minutes=1),
        )

        engine.on_broker_event(broker_event_from_order(submitted))

        tracked_order = engine.order_manager.get_order(order.order_id)
        self.assertEqual(tracked_order.status, OrderStatus.SUBMITTED)

    def test_in_memory_broker_event_source_yields_normalized_events(self) -> None:
        broker = BacktestBrokerage(starting_cash=10000)
        broker.connect()
        order = broker.submit_order(build_order_request(approved_decision()))
        fill = broker.on_market_event(bar(1, open_price=100))[0]
        source = InMemoryBrokerEventSource(
            [
                broker_event_from_order(order),
                broker_event_from_fill(fill),
            ]
        )

        events = list(source.iter_events())
        source.close()

        self.assertEqual([event.event_type for event in events], [BrokerEventType.ORDER_UPDATE, BrokerEventType.FILL])
        self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
