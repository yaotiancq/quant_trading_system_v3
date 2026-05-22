from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.domain import OrderRequest, OrderSide, OrderStatus, OrderType, TimeInForce
from qts.integrations.alpaca import (
    alpaca_account_to_domain,
    alpaca_order_to_domain,
    alpaca_order_to_fill_delta,
    alpaca_position_to_domain,
    order_request_to_alpaca_payload,
)


NOW_TEXT = "2026-01-05T14:30:00Z"
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_order_request() -> OrderRequest:
    return OrderRequest(
        client_order_id="coid-1",
        strategy_id="strategy-1",
        symbol="spy",
        timestamp=NOW,
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=100.25,
        time_in_force=TimeInForce.DAY,
        metadata={"extended_hours": True},
    )


def make_alpaca_order(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "alpaca-order-1",
        "client_order_id": "coid-1",
        "symbol": "SPY",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "qty": "10",
        "filled_qty": "0",
        "filled_avg_price": None,
        "status": "new",
        "created_at": NOW_TEXT,
        "submitted_at": NOW_TEXT,
        "updated_at": NOW_TEXT,
        "limit_price": None,
        "stop_price": None,
    }
    payload.update(overrides)
    return payload


class AlpacaMappingTests(unittest.TestCase):
    def test_order_request_payload_uses_alpaca_field_names(self) -> None:
        payload = order_request_to_alpaca_payload(make_order_request())

        self.assertEqual(payload["symbol"], "SPY")
        self.assertEqual(payload["side"], "buy")
        self.assertEqual(payload["type"], "limit")
        self.assertEqual(payload["time_in_force"], "day")
        self.assertEqual(payload["qty"], "10")
        self.assertEqual(payload["limit_price"], "100.25")
        self.assertTrue(payload["extended_hours"])

    def test_order_response_maps_status_and_fill_fields(self) -> None:
        order = alpaca_order_to_domain(
            make_alpaca_order(
                status="partially_filled",
                filled_qty="4",
                filled_avg_price="101.50",
            )
        )

        self.assertEqual(order.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(order.filled_quantity, 4)
        self.assertEqual(order.remaining_quantity, 6)
        self.assertEqual(order.average_fill_price, 101.50)

    def test_fill_delta_uses_incremental_filled_quantity(self) -> None:
        fill = alpaca_order_to_fill_delta(
            make_alpaca_order(
                status="filled",
                filled_qty="10",
                filled_avg_price="101",
                filled_at="2026-01-05T14:31:00Z",
            ),
            previous_filled_quantity=4,
        )

        self.assertIsNotNone(fill)
        assert fill is not None
        self.assertEqual(fill.fill_id, "alpaca-fill-alpaca-order-1-10")
        self.assertEqual(fill.quantity, 6)
        self.assertEqual(fill.price, 101)
        self.assertEqual(fill.source, "alpaca_paper")

    def test_account_and_position_payloads_map_to_domain_models(self) -> None:
        account = alpaca_account_to_domain(
            {
                "id": "acct-1",
                "currency": "USD",
                "cash": "99000.50",
                "equity": "100010.50",
                "buying_power": "99000.50",
                "long_market_value": "1010",
                "short_market_value": "0",
                "status": "ACTIVE",
                "created_at": NOW_TEXT,
            }
        )
        position = alpaca_position_to_domain(
            {
                "symbol": "spy",
                "qty": "10",
                "avg_entry_price": "100",
                "current_price": "101",
                "market_value": "1010",
                "unrealized_pl": "10",
            }
        )

        self.assertEqual(account.account_id, "acct-1")
        self.assertEqual(account.cash, 99000.50)
        self.assertEqual(position.symbol, "SPY")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.market_value, 1010)


if __name__ == "__main__":
    unittest.main()
