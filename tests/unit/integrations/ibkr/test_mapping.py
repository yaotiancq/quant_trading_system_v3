from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.core import BrokerError
from qts.domain import OrderRequest, OrderSide, OrderStatus, OrderType, TimeInForce
from qts.integrations.ibkr import (
    first_order_ack,
    ibkr_account_to_domain,
    ibkr_order_to_domain,
    ibkr_order_to_fill_delta,
    ibkr_position_to_domain,
    is_order_reply_required,
    order_request_to_ibkr_payload,
)


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
NOW_TEXT = "2026-01-05T14:30:00Z"


def make_order_request(**overrides: object) -> OrderRequest:
    data: dict[str, object] = {
        "client_order_id": "coid-1",
        "strategy_id": "strategy-1",
        "symbol": "spy",
        "timestamp": NOW,
        "side": OrderSide.BUY,
        "quantity": 10,
        "order_type": OrderType.LIMIT,
        "limit_price": 100.25,
        "time_in_force": TimeInForce.DAY,
        "metadata": {"outside_rth": True},
    }
    data.update(overrides)
    return OrderRequest(**data)


def make_ibkr_order(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "order_id": "ibkr-order-1",
        "cOID": "coid-1",
        "ticker": "SPY",
        "side": "BUY",
        "orderType": "LMT",
        "quantity": 10,
        "filledQuantity": 0,
        "avgPrice": None,
        "order_status": "Submitted",
        "created_at": NOW_TEXT,
        "updated_at": NOW_TEXT,
        "price": 100.25,
        "conid": 756733,
    }
    payload.update(overrides)
    return payload


class IBKRMappingTests(unittest.TestCase):
    def test_order_request_payload_uses_conid_and_ibkr_field_names(self) -> None:
        payload = order_request_to_ibkr_payload(
            make_order_request(),
            symbol_conids={"SPY": 756733},
        )

        self.assertEqual(payload["conid"], 756733)
        self.assertEqual(payload["side"], "BUY")
        self.assertEqual(payload["orderType"], "LMT")
        self.assertEqual(payload["quantity"], 10)
        self.assertEqual(payload["price"], 100.25)
        self.assertTrue(payload["outsideRTH"])

    def test_order_request_requires_conid_and_quantity(self) -> None:
        with self.assertRaises(BrokerError):
            order_request_to_ibkr_payload(make_order_request(), symbol_conids={})

        with self.assertRaises(BrokerError):
            order_request_to_ibkr_payload(
                make_order_request(quantity=None, notional=1000, metadata={"conid": 756733})
            )

    def test_order_response_maps_status_and_fill_fields(self) -> None:
        order = ibkr_order_to_domain(
            make_ibkr_order(
                order_status="Filled",
                filledQuantity=10,
                avgPrice=101.50,
            )
        )

        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.filled_quantity, 10)
        self.assertEqual(order.remaining_quantity, 0)
        self.assertEqual(order.average_fill_price, 101.50)

    def test_fill_delta_uses_incremental_filled_quantity(self) -> None:
        fill = ibkr_order_to_fill_delta(
            make_ibkr_order(
                order_status="Filled",
                filledQuantity=10,
                avgPrice=101,
                updated_at="2026-01-05T14:31:00Z",
            ),
            previous_filled_quantity=4,
        )

        self.assertIsNotNone(fill)
        assert fill is not None
        self.assertEqual(fill.fill_id, "ibkr-fill-ibkr-order-1-10")
        self.assertEqual(fill.quantity, 6)
        self.assertEqual(fill.price, 101)
        self.assertEqual(fill.source, "ibkr")

    def test_account_and_position_payloads_map_to_domain_models(self) -> None:
        account = ibkr_account_to_domain(
            {
                "accountId": "DU123456",
                "currency": "USD",
                "totalcashvalue": {"amount": 99000.50, "currency": "USD"},
                "netliquidation": {"amount": 100010.50, "currency": "USD"},
                "buyingpower": {"amount": 99000.50, "currency": "USD"},
                "grosspositionvalue": {"amount": 1010, "currency": "USD"},
            }
        )
        position = ibkr_position_to_domain(
            {
                "ticker": "spy",
                "position": "10",
                "avgCost": "100",
                "mktPrice": "101",
                "mktValue": "1010",
                "unrealizedPnl": "10",
            }
        )

        self.assertEqual(account.account_id, "DU123456")
        self.assertEqual(account.cash, 99000.50)
        self.assertEqual(position.symbol, "SPY")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.market_value, 1010)

    def test_reply_required_response_is_not_treated_as_acknowledgement(self) -> None:
        response = [{"id": "reply-1", "message": ["precautionary order prompt"]}]

        self.assertTrue(is_order_reply_required(response))
        with self.assertRaises(BrokerError):
            first_order_ack(response)


if __name__ == "__main__":
    unittest.main()
