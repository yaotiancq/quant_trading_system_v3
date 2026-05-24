from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.brokers.alpaca import AlpacaBrokerage
from qts.core import BrokerError, ConfigurationError, LiveSafetyError
from qts.domain import BrokerConfig, OrderRequest, OrderSide, OrderStatus, OrderType, TimeInForce
from qts.integrations.alpaca import AlpacaAPIError


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
NOW_TEXT = "2026-01-05T14:30:00Z"


class FakeAlpacaClient:
    def __init__(self) -> None:
        self.submitted_payloads: list[dict[str, object]] = []
        self.order = {
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
        }

    def get_account(self) -> dict[str, object]:
        return {
            "id": "acct-1",
            "currency": "USD",
            "cash": "100000",
            "equity": "100000",
            "buying_power": "100000",
            "long_market_value": "0",
            "short_market_value": "0",
            "created_at": NOW_TEXT,
        }

    def list_positions(self) -> list[dict[str, object]]:
        return []

    def submit_order(self, payload: dict[str, object]) -> dict[str, object]:
        self.submitted_payloads.append(dict(payload))
        return dict(self.order)

    def cancel_order(self, order_id: str) -> dict[str, object]:
        self.order["status"] = "canceled"
        return dict(self.order)

    def get_order(self, order_id: str) -> dict[str, object]:
        return dict(self.order)

    def list_orders(self, **kwargs: object) -> list[dict[str, object]]:
        return [dict(self.order)]

    def get_clock(self) -> dict[str, object]:
        return {"is_open": True, "timestamp": NOW_TEXT}

    def close(self) -> None:
        return None


def make_config(**overrides: object) -> BrokerConfig:
    data = {
        "broker_type": "alpaca_paper",
        "paper": True,
        "credential_env_keys": {
            "api_key_id": "ALPACA_API_KEY_ID",
            "secret_key": "ALPACA_SECRET_KEY",
        },
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


class AlpacaBrokerageTests(unittest.TestCase):
    def test_submit_order_converts_request_and_caches_domain_order(self) -> None:
        client = FakeAlpacaClient()
        broker = AlpacaBrokerage(make_config(), client=client)
        broker.connect()

        order = broker.submit_order(make_order_request())

        self.assertEqual(order.order_id, "alpaca-order-1")
        self.assertEqual(order.status, OrderStatus.SUBMITTED)
        self.assertEqual(order.metadata["strategy_id"], "strategy-1")
        self.assertEqual(client.submitted_payloads[0]["qty"], "10")
        self.assertEqual(client.submitted_payloads[0]["side"], "buy")

    def test_poll_fills_returns_only_new_filled_quantity(self) -> None:
        client = FakeAlpacaClient()
        broker = AlpacaBrokerage(make_config(), client=client)
        broker.connect()
        broker.submit_order(make_order_request())

        client.order.update(
            {
                "status": "filled",
                "filled_qty": "10",
                "filled_avg_price": "101",
                "filled_at": "2026-01-05T14:31:00Z",
                "updated_at": "2026-01-05T14:31:00Z",
            }
        )
        first = broker.poll_fills()
        second = broker.poll_fills()

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].quantity, 10)
        self.assertEqual(first[0].price, 101)
        self.assertEqual(second, [])

    def test_broker_errors_are_normalized(self) -> None:
        class FailingClient(FakeAlpacaClient):
            def submit_order(self, payload: dict[str, object]) -> dict[str, object]:
                raise AlpacaAPIError("boom", status_code=403)

        broker = AlpacaBrokerage(make_config(), client=FailingClient())
        broker.connect()

        with self.assertRaises(BrokerError):
            broker.submit_order(make_order_request())

    def test_ungated_live_alpaca_configuration_fails_closed(self) -> None:
        broker = AlpacaBrokerage(
            make_config(broker_type="alpaca_live", paper=False),
            client=FakeAlpacaClient(),
        )

        with self.assertRaises(LiveSafetyError):
            broker.connect()

    def test_live_alpaca_requires_explicit_submission_safety_gates(self) -> None:
        broker = AlpacaBrokerage(
            make_config(
                broker_type="alpaca_live",
                paper=False,
                safety={
                    "live_enabled": True,
                    "dry_run": False,
                    "mock_mode": False,
                    "confirm_live_trading": True,
                },
            ),
            client=FakeAlpacaClient(),
        )

        with self.assertRaisesRegex(LiveSafetyError, "enable_order_submission"):
            broker.connect()

    def test_live_alpaca_connects_with_injected_client_after_safety_gates(self) -> None:
        client = FakeAlpacaClient()
        broker = AlpacaBrokerage(
            make_config(
                broker_type="alpaca_live",
                paper=False,
                safety={
                    "live_enabled": True,
                    "dry_run": False,
                    "mock_mode": False,
                    "confirm_live_trading": True,
                    "enable_order_submission": True,
                },
            ),
            client=client,
        )

        broker.connect()
        order = broker.submit_order(make_order_request())

        self.assertEqual(order.order_id, "alpaca-order-1")
        self.assertEqual(client.submitted_payloads[0]["symbol"], "SPY")

    def test_live_alpaca_without_injected_client_requires_credentials(self) -> None:
        broker = AlpacaBrokerage(
            make_config(
                broker_type="alpaca_live",
                paper=False,
                safety={
                    "live_enabled": True,
                    "dry_run": False,
                    "mock_mode": False,
                    "confirm_live_trading": True,
                    "enable_order_submission": True,
                },
            ),
            env_values={},
        )

        with self.assertRaisesRegex(ConfigurationError, "missing Alpaca credential"):
            broker.connect()


if __name__ == "__main__":
    unittest.main()
