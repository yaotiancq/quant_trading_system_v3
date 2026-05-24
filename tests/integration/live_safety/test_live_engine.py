from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO

from qts.core import LiveSafetyError, ReplayClock
from qts.domain import (
    Account,
    Bar,
    BarTimeframe,
    Fill,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
    Quote,
    Signal,
    SignalDirection,
    TimeInForce,
)
from qts.engines import LiveEngine
from qts.execution import InMemoryBrokerEventSource, broker_event_from_order
from qts.strategies import BaseStrategy

from scripts.run_live_trading import main as run_live_main
from tests.unit.monitoring.helpers import NOW, make_live_config


class BuyOnceLiveStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__()
        self.fired = False

    def on_data(
        self,
        market_event: Bar,
        features,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self._validate_symbol(market_event.symbol)
        if self.fired:
            return []
        self.fired = True
        return [
            Signal(
                signal_id="live-preview-buy-once",
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=SignalDirection.BUY,
                confidence=1.0,
                reason="live_preview_test",
            )
        ]


def make_bar() -> Bar:
    return Bar(
        symbol="SPY",
        timestamp=NOW,
        timeframe=BarTimeframe.MINUTE,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1000,
    )


class RecordingLiveBrokerage:
    def __init__(self, account_id: str = "acct-1") -> None:
        self.connected = False
        self.submitted_requests: list[OrderRequest] = []
        self.orders: dict[str, Order] = {}
        self.account = Account(
            account_id=account_id,
            timestamp=NOW,
            currency="USD",
            cash=100000,
            equity=100000,
            buying_power=100000,
        )

    def connect(self, broker_config=None) -> None:  # type: ignore[no-untyped-def]
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def submit_order(self, order_request: OrderRequest) -> Order:
        self.submitted_requests.append(order_request)
        order = Order(
            order_id=f"live-order-{len(self.submitted_requests)}",
            client_order_id=order_request.client_order_id,
            symbol=order_request.symbol,
            created_at=order_request.timestamp,
            updated_at=order_request.timestamp,
            side=order_request.side,
            quantity=order_request.quantity,
            filled_quantity=0,
            remaining_quantity=order_request.quantity,
            order_type=order_request.order_type,
            status=OrderStatus.ACCEPTED,
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            metadata=dict(order_request.metadata),
        )
        self.orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: str) -> Order:
        return self.orders[order_id]

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def list_orders(self, status=None, symbol=None) -> list[Order]:  # type: ignore[no-untyped-def]
        return list(self.orders.values())

    def get_account(self) -> Account:
        return self.account

    def get_positions(self) -> list[Position]:
        return []

    def poll_fills(self, since=None) -> list[Fill]:  # type: ignore[no-untyped-def]
        return []

    def is_market_open(self, timestamp) -> bool:  # type: ignore[no-untyped-def]
        return True


class LiveEngineSafetyIntegrationTests(unittest.TestCase):
    def test_dry_run_live_engine_initializes_and_starts(self) -> None:
        engine = LiveEngine(make_live_config())

        health = engine.start(max_events=0)

        self.assertTrue(health["initialized"])
        self.assertTrue(health["dry_run"])
        self.assertEqual(health["status"], "OK")
        engine.stop(reason="test complete")

    def test_live_engine_health_uses_market_session_service(self) -> None:
        holiday_clock = ReplayClock(datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))
        engine = LiveEngine(make_live_config(), clock=holiday_clock)

        health = engine.start(max_events=0)

        broker_check = next(check for check in health["checks"] if check["name"] == "broker_connection")
        self.assertFalse(broker_check["details"]["market_open"])
        engine.stop(reason="test complete")

    def test_live_engine_rejects_missing_safety_enablement(self) -> None:
        engine = LiveEngine(make_live_config(safety={"live_enabled": False}))

        with self.assertRaises(LiveSafetyError):
            engine.initialize()

    def test_live_engine_exposes_order_safety_validation(self) -> None:
        engine = LiveEngine(make_live_config())
        engine.initialize()
        order = OrderRequest(
            client_order_id="too-large",
            strategy_id="sma_live",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=11,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        with self.assertRaises(LiveSafetyError):
            engine.validate_order_request(order, price=100)

    def test_live_engine_records_safety_approved_decision_preview_without_submission(self) -> None:
        config = make_live_config(
            risk={
                "sizing_method": "fixed_quantity",
                "sizing_parameters": {"quantity": 1},
            },
            execution={"allow_fractional": False},
        )
        engine = LiveEngine(config, strategies=[BuyOnceLiveStrategy()])
        engine.initialize()

        status = engine.on_market_event(make_bar())

        previews = status["decision_previews"]
        self.assertEqual(len(previews), 1)
        self.assertEqual(previews[0]["preview_status"], "safety_approved")
        self.assertTrue(previews[0]["would_submit"])
        self.assertEqual(previews[0]["order_request"]["symbol"], "SPY")
        self.assertEqual(status["decision_preview_count"], 1)
        self.assertEqual(engine.brokerage.orders, {})

    def test_live_engine_records_safety_rejected_decision_preview(self) -> None:
        config = make_live_config(
            risk={
                "sizing_method": "fixed_quantity",
                "sizing_parameters": {"quantity": 11},
            },
            execution={"allow_fractional": False},
        )
        engine = LiveEngine(config, strategies=[BuyOnceLiveStrategy()])
        engine.initialize()

        status = engine.on_market_event(make_bar())

        preview = status["decision_previews"][0]
        self.assertEqual(preview["preview_status"], "safety_rejected")
        self.assertFalse(preview["would_submit"])
        self.assertIn("max_order_quantity", preview["error"])
        self.assertEqual(engine.brokerage.orders, {})

    def test_live_engine_quote_event_updates_state_without_decision_preview(self) -> None:
        engine = LiveEngine(make_live_config(), strategies=[BuyOnceLiveStrategy()])
        engine.initialize()
        quote = Quote(
            symbol="SPY",
            timestamp=NOW,
            bid_price=100,
            ask_price=100.1,
        )

        status = engine.on_market_event(quote)

        self.assertEqual(status["decision_previews"], [])
        self.assertEqual(status["decision_preview_count"], 0)
        self.assertEqual(status["last_market_event_symbol"], "SPY")

    def test_live_engine_syncs_broker_event_source_without_submission(self) -> None:
        engine = LiveEngine(make_live_config())
        engine.initialize()
        order = Order(
            order_id="live-restart-order-1",
            client_order_id="coid-live-restart-order-1",
            symbol="SPY",
            created_at=NOW,
            updated_at=NOW,
            side=OrderSide.BUY,
            filled_quantity=0,
            order_type=OrderType.MARKET,
            status=OrderStatus.ACCEPTED,
            quantity=1,
            remaining_quantity=1,
        )
        source = InMemoryBrokerEventSource([broker_event_from_order(order)])

        result = engine.sync_broker_events(source, max_events=1)

        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(result["checkpoint"]["processed_event_count"], 1)
        self.assertEqual(result["reconciliation_before"]["status"], "matched")
        self.assertEqual(result["reconciliation_after"]["status"], "matched")
        self.assertEqual(engine.health_check()["broker_event_sync"]["processed_count"], 1)
        self.assertEqual(engine.brokerage.orders, {})
        self.assertTrue(source.closed)

    def test_live_engine_manual_submission_requires_submission_flag(self) -> None:
        config = make_live_config(
            safety={
                "dry_run": False,
                "mock_mode": False,
                "confirm_live_trading": True,
            }
        )
        brokerage = RecordingLiveBrokerage()
        engine = LiveEngine(config, brokerage=brokerage)
        engine.initialize()
        order_request = OrderRequest(
            client_order_id="manual-live-blocked",
            strategy_id="manual",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        with self.assertRaisesRegex(LiveSafetyError, "enable_order_submission"):
            engine.submit_live_order(order_request, price=100)

        self.assertEqual(brokerage.submitted_requests, [])

    def test_live_engine_manual_submission_uses_broker_after_all_safety_gates(self) -> None:
        config = make_live_config(
            safety={
                "dry_run": False,
                "mock_mode": False,
                "confirm_live_trading": True,
                "enable_order_submission": True,
            }
        )
        brokerage = RecordingLiveBrokerage()
        engine = LiveEngine(config, brokerage=brokerage)
        engine.initialize()
        order_request = OrderRequest(
            client_order_id="manual-live-ok",
            strategy_id="manual",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        result = engine.submit_live_order(order_request, price=100)

        self.assertTrue(result["submitted"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["order_id"], "live-order-1")
        self.assertEqual(result["reconciliation"]["status"], "matched")
        self.assertEqual(len(brokerage.submitted_requests), 1)
        self.assertEqual(engine.health_check()["live_order_submission_count"], 1)
        self.assertEqual(
            engine.health_check()["last_live_order_submission"]["order_id"],
            "live-order-1",
        )

    def test_live_runner_dry_run_command_initializes(self) -> None:
        with redirect_stdout(StringIO()):
            exit_code = run_live_main(
                [
                    "--config",
                    "configs/live_alpaca.yaml",
                    "--dry-run",
                    "--confirm-live-safety",
                ]
            )

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
