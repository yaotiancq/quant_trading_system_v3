from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.brokers.ibkr import IBKRBrokerage
from qts.core import BrokerError, LiveSafetyError
from qts.domain import BrokerConfig, OrderRequest, OrderSide, OrderStatus, OrderType, TimeInForce
from qts.integrations.ibkr import InMemoryIBKRClient


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_config(**overrides: object) -> BrokerConfig:
    data = {
        "broker_type": "ibkr_paper",
        "paper": True,
        "account_id": "DU123456",
        "credential_env_keys": {"access_token": "IBKR_ACCESS_TOKEN"},
        "safety": {"symbol_conids": {"SPY": 756733}},
    }
    data.update(overrides)
    return BrokerConfig(**data)


def make_order_request() -> OrderRequest:
    return OrderRequest(
        client_order_id="coid-1",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=NOW,
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
    )


class IBKRBrokerageTests(unittest.TestCase):
    def test_submit_order_converts_request_and_caches_domain_order(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456")
        broker = IBKRBrokerage(make_config(), client=client)
        broker.connect()

        order = broker.submit_order(make_order_request())

        self.assertEqual(order.order_id, "mock-ibkr-order-000001")
        self.assertEqual(order.status, OrderStatus.SUBMITTED)
        self.assertEqual(order.metadata["strategy_id"], "strategy-1")
        self.assertEqual(client.submitted_payloads[0]["conid"], 756733)
        self.assertEqual(client.submitted_payloads[0]["side"], "BUY")

    def test_poll_fills_returns_only_new_filled_quantity(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456", fill_immediately=True, fill_price=101)
        broker = IBKRBrokerage(make_config(), client=client)
        broker.connect()
        broker.submit_order(make_order_request())

        first = broker.poll_fills()
        second = broker.poll_fills()

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].quantity, 10)
        self.assertEqual(first[0].price, 101)
        self.assertEqual(first[0].source, "ibkr_paper")
        self.assertEqual(second, [])

    def test_poll_fills_excludes_fill_at_since_boundary(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456", fill_immediately=True, fill_price=101)
        broker = IBKRBrokerage(make_config(), client=client)
        broker.connect()
        broker.submit_order(make_order_request())
        first = broker.poll_fills()
        order_id = first[0].order_id
        client.orders[order_id]["filledQuantity"] = 11
        client.orders[order_id]["updated_at"] = first[0].timestamp.isoformat()

        boundary = broker.poll_fills(since=first[0].timestamp)

        self.assertEqual(boundary, [])

        client.orders[order_id]["filledQuantity"] = 12
        client.orders[order_id]["updated_at"] = (first[0].timestamp + timedelta(seconds=1)).isoformat()
        after_boundary = broker.poll_fills(since=first[0].timestamp)

        self.assertEqual(len(after_boundary), 1)
        self.assertEqual(after_boundary[0].quantity, 1)

    def test_poll_fills_excludes_fill_before_since_boundary(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456", fill_immediately=True, fill_price=101)
        broker = IBKRBrokerage(make_config(), client=client)
        broker.connect()
        broker.submit_order(make_order_request())
        first = broker.poll_fills()
        order_id = first[0].order_id
        client.orders[order_id]["filledQuantity"] = 11
        client.orders[order_id]["updated_at"] = first[0].timestamp.isoformat()

        before_boundary = broker.poll_fills(since=first[0].timestamp + timedelta(seconds=1))

        self.assertEqual(before_boundary, [])

    def test_reply_required_response_is_rejected_fail_closed(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456", require_order_reply=True)
        broker = IBKRBrokerage(make_config(), client=client)
        broker.connect()

        with self.assertRaises(BrokerError):
            broker.submit_order(make_order_request())

    def test_live_ibkr_configuration_is_rejected(self) -> None:
        broker = IBKRBrokerage(
            make_config(broker_type="ibkr_live", paper=False),
            client=InMemoryIBKRClient(account_id="DU123456"),
        )

        with self.assertRaises(LiveSafetyError):
            broker.connect()

    def test_missing_conid_is_rejected_before_submission(self) -> None:
        client = InMemoryIBKRClient(account_id="DU123456")
        broker = IBKRBrokerage(make_config(safety={}), client=client)
        broker.connect()

        with self.assertRaises(BrokerError):
            broker.submit_order(make_order_request())


if __name__ == "__main__":
    unittest.main()
