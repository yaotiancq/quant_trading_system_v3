from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.domain import Fill, Order, OrderSide, OrderStatus, OrderType
from qts.portfolio import DefaultPortfolio


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def make_order(order_id: str = "order-1") -> Order:
    return Order(
        order_id=order_id,
        client_order_id=f"coid-{order_id}",
        symbol="SPY",
        created_at=NOW,
        updated_at=NOW,
        side=OrderSide.BUY,
        quantity=10,
        filled_quantity=10,
        remaining_quantity=0,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        metadata={"strategy_id": "strategy-1"},
    )


def make_fill(
    fill_id: str,
    *,
    side: OrderSide,
    quantity: float,
    price: float,
    commission: float = 0.0,
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id="order-1",
        client_order_id="coid-order-1",
        symbol="SPY",
        timestamp=NOW,
        side=side,
        quantity=quantity,
        price=price,
        commission=commission,
        source="unit_test",
    )


class PortfolioAccountingTests(unittest.TestCase):
    def test_buy_fill_updates_cash_position_and_ledgers(self) -> None:
        portfolio = DefaultPortfolio(10000, timestamp=NOW)

        snapshot = portfolio.apply_fill(
            make_fill("fill-buy", side=OrderSide.BUY, quantity=10, price=100, commission=1),
            make_order(),
        )

        position = portfolio.get_position("SPY")
        self.assertEqual(snapshot.cash, 8999)
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.average_cost, 100)
        self.assertEqual(len(portfolio.get_trade_ledger()), 1)
        self.assertEqual(len(portfolio.get_cash_ledger()), 2)
        self.assertEqual(portfolio.get_trade_ledger()[0].strategy_id, "strategy-1")

    def test_sell_fill_updates_realized_pnl_and_remaining_position(self) -> None:
        portfolio = DefaultPortfolio(10000, timestamp=NOW)
        portfolio.apply_fill(
            make_fill("fill-buy", side=OrderSide.BUY, quantity=10, price=100, commission=1),
            make_order(),
        )

        snapshot = portfolio.apply_fill(
            make_fill("fill-sell", side=OrderSide.SELL, quantity=4, price=110, commission=1),
            make_order(),
        )

        position = portfolio.get_position("SPY")
        self.assertEqual(position.quantity, 6)
        self.assertEqual(position.average_cost, 100)
        self.assertEqual(snapshot.realized_pnl, 39)
        self.assertEqual(snapshot.cash, 9438)
        self.assertEqual(portfolio.get_trade_ledger()[-1].realized_pnl_delta, 39)

    def test_mark_to_market_records_unrealized_pnl_and_equity(self) -> None:
        portfolio = DefaultPortfolio(10000, timestamp=NOW)
        portfolio.apply_fill(
            make_fill("fill-buy", side=OrderSide.BUY, quantity=10, price=100),
            make_order(),
        )

        snapshot = portfolio.mark_to_market({"SPY": 110}, NOW)

        self.assertEqual(snapshot.unrealized_pnl, 100)
        self.assertEqual(snapshot.positions_value, 1100)
        self.assertEqual(snapshot.equity, 10100)


if __name__ == "__main__":
    unittest.main()
