from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO

from qts.core import LiveSafetyError, ReplayClock
from qts.domain import OrderRequest, OrderSide, OrderType, TimeInForce
from qts.engines import LiveEngine

from scripts.run_live_trading import main as run_live_main
from tests.unit.monitoring.helpers import NOW, make_live_config


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
