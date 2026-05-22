from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.domain import Account, Fill, OrderSide, Position
from qts.portfolio import DefaultPortfolio


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_buy_fill() -> Fill:
    return Fill(
        fill_id="fill-1",
        order_id="order-1",
        client_order_id="coid-1",
        symbol="SPY",
        timestamp=NOW,
        side=OrderSide.BUY,
        quantity=10,
        price=100,
        commission=0,
        source="unit_test",
    )


class PortfolioReconciliationTests(unittest.TestCase):
    def test_reconciliation_reports_matched_state(self) -> None:
        portfolio = DefaultPortfolio(10000, timestamp=NOW)
        portfolio.apply_fill(make_buy_fill())
        account = portfolio.get_account()
        position = portfolio.get_position("SPY")

        result = portfolio.reconcile(account, [position])

        self.assertTrue(result["matched"])
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["position_differences"], [])

    def test_reconciliation_reports_cash_and_position_mismatches(self) -> None:
        portfolio = DefaultPortfolio(10000, timestamp=NOW)
        portfolio.apply_fill(make_buy_fill())
        broker_account = Account(
            account_id="broker",
            timestamp=NOW,
            currency="USD",
            cash=8000,
            equity=9000,
            buying_power=8000,
        )
        broker_position = Position(
            symbol="SPY",
            quantity=9,
            average_cost=100,
            market_price=100,
            updated_at=NOW,
        )

        result = portfolio.reconcile(broker_account, [broker_position])

        self.assertFalse(result["matched"])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["cash_difference"], 1000)
        self.assertEqual(len(result["position_differences"]), 1)
        self.assertEqual(result["position_differences"][0]["quantity_difference"], 1)


if __name__ == "__main__":
    unittest.main()
