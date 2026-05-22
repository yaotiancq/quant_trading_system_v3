from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.brokers.backtest import BacktestBrokerage
from qts.domain import (
    Bar,
    BarTimeframe,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Quote,
    TimeInForce,
)


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def make_broker(**kwargs: object) -> BacktestBrokerage:
    broker = BacktestBrokerage(**kwargs)
    broker.connect()
    return broker


def make_order_request(
    *,
    side: OrderSide = OrderSide.BUY,
    order_type: OrderType = OrderType.MARKET,
    quantity: float | None = 10.0,
    notional: float | None = None,
    limit_price: float | None = None,
    stop_price: float | None = None,
    timestamp: datetime = NOW,
) -> OrderRequest:
    return OrderRequest(
        client_order_id=f"coid-{order_type.value.lower()}-{timestamp.strftime('%H%M%S')}",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=timestamp,
        side=side,
        quantity=quantity,
        notional=notional,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=stop_price,
        time_in_force=TimeInForce.DAY,
    )


def make_bar(
    minutes: int,
    *,
    open_price: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    close: float | None = None,
) -> Bar:
    high_value = open_price + 1 if high is None else high
    low_value = open_price - 1 if low is None else low
    close_value = open_price if close is None else close
    return Bar(
        symbol="SPY",
        timestamp=NOW + timedelta(minutes=minutes),
        timeframe=BarTimeframe.MINUTE,
        open=open_price,
        high=high_value,
        low=low_value,
        close=close_value,
        volume=1000,
    )


class BacktestBrokerageTests(unittest.TestCase):
    def test_market_order_fills_on_next_bar_open_and_updates_account_state(self) -> None:
        broker = make_broker(starting_cash=10000)
        order = broker.submit_order(make_order_request())

        self.assertEqual(broker.on_market_event(make_bar(0, open_price=90)), [])
        fills = broker.on_market_event(make_bar(1, open_price=100))

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, 100)
        self.assertEqual(broker.get_order(order.order_id).status, OrderStatus.FILLED)
        self.assertEqual(broker.get_account().cash, 9000)
        positions = broker.get_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].quantity, 10)
        self.assertEqual(positions[0].average_cost, 100)

    def test_limit_order_fills_when_bar_touches_limit_price(self) -> None:
        broker = make_broker(starting_cash=10000)
        order = broker.submit_order(
            make_order_request(order_type=OrderType.LIMIT, limit_price=99)
        )

        fills = broker.on_market_event(make_bar(1, open_price=100, high=101, low=98))

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, 99)
        self.assertEqual(broker.get_order(order.order_id).status, OrderStatus.FILLED)

    def test_stop_order_fills_when_bar_crosses_stop_price(self) -> None:
        broker = make_broker(starting_cash=10000)
        order = broker.submit_order(
            make_order_request(order_type=OrderType.STOP, stop_price=105)
        )

        self.assertEqual(broker.on_market_event(make_bar(1, open_price=103, high=104, low=102)), [])
        fills = broker.on_market_event(make_bar(2, open_price=104, high=106, low=103))

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, 105)
        self.assertEqual(broker.get_order(order.order_id).status, OrderStatus.FILLED)

    def test_insufficient_buying_power_rejects_order_at_fill_time(self) -> None:
        broker = make_broker(starting_cash=10000)
        order = broker.submit_order(make_order_request(quantity=200))

        fills = broker.on_market_event(make_bar(1, open_price=100))
        rejected = broker.get_order(order.order_id)

        self.assertEqual(fills, [])
        self.assertEqual(rejected.status, OrderStatus.REJECTED)
        self.assertEqual(rejected.rejection_reason, "insufficient_buying_power")
        self.assertEqual(broker.get_positions(), [])

    def test_slippage_and_commission_are_applied_to_fill_and_cash(self) -> None:
        broker = make_broker(
            starting_cash=10000,
            slippage_model={"type": "bps", "value": 10},
            commission_model={"type": "per_share", "value": 0.01},
        )
        broker.submit_order(make_order_request())

        fills = broker.on_market_event(make_bar(1, open_price=100))
        account = broker.get_account()

        self.assertAlmostEqual(fills[0].price, 100.10)
        self.assertAlmostEqual(fills[0].slippage, 0.10)
        self.assertAlmostEqual(fills[0].commission, 0.10)
        self.assertAlmostEqual(account.cash, 8998.90)

    def test_quote_bid_ask_policy_uses_ask_for_buy_orders(self) -> None:
        broker = make_broker(starting_cash=10000, fill_policy="quote_bid_ask")
        broker.submit_order(make_order_request())

        fills = broker.on_market_event(
            Quote(
                symbol="SPY",
                timestamp=NOW + timedelta(minutes=1),
                bid_price=99,
                ask_price=101,
            )
        )

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, 101)

    def test_cancelled_order_does_not_fill(self) -> None:
        broker = make_broker(starting_cash=10000)
        order = broker.submit_order(make_order_request())

        canceled = broker.cancel_order(order.order_id)
        fills = broker.on_market_event(make_bar(1, open_price=100))

        self.assertEqual(canceled.status, OrderStatus.CANCELED)
        self.assertEqual(fills, [])
        self.assertEqual(broker.get_account().cash, 10000)

    def test_partial_fills_complete_over_multiple_market_events(self) -> None:
        broker = make_broker(starting_cash=10000, max_fill_quantity_per_event=5)
        order = broker.submit_order(make_order_request(quantity=12))

        broker.on_market_event(make_bar(1, open_price=100))
        first_update = broker.get_order(order.order_id)
        broker.on_market_event(make_bar(2, open_price=100))
        second_update = broker.get_order(order.order_id)
        broker.on_market_event(make_bar(3, open_price=100))
        final_update = broker.get_order(order.order_id)

        self.assertEqual(first_update.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(first_update.filled_quantity, 5)
        self.assertEqual(first_update.remaining_quantity, 7)
        self.assertEqual(second_update.filled_quantity, 10)
        self.assertEqual(final_update.status, OrderStatus.FILLED)
        self.assertEqual(final_update.filled_quantity, 12)
        self.assertEqual(broker.get_account().cash, 8800)


if __name__ == "__main__":
    unittest.main()
