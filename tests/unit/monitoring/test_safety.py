from __future__ import annotations

import unittest

from qts.core import LiveSafetyError
from qts.domain import Account, OrderRequest, OrderSide, OrderType, TimeInForce
from qts.monitoring import (
    validate_live_account,
    validate_live_order_submission_config,
    validate_live_safety_config,
    validate_order_request_safety,
)

from .helpers import NOW, make_live_config


class LiveSafetyTests(unittest.TestCase):
    def test_live_safety_requires_explicit_enablement(self) -> None:
        config = make_live_config(safety={"live_enabled": False})

        with self.assertRaises(LiveSafetyError):
            validate_live_safety_config(config)

    def test_live_safety_accepts_explicit_dry_run_policy(self) -> None:
        config = make_live_config()

        policy = validate_live_safety_config(config)

        self.assertTrue(policy.live_enabled)
        self.assertTrue(policy.dry_run)
        self.assertFalse(policy.order_submission_enabled)
        self.assertEqual(policy.allowed_symbols, ["SPY"])

    def test_live_order_submission_requires_non_dry_run_explicit_enablement(self) -> None:
        dry_run_config = make_live_config()
        missing_submission_flag = make_live_config(
            safety={
                "dry_run": False,
                "mock_mode": False,
                "confirm_live_trading": True,
            }
        )
        enabled_config = make_live_config(
            safety={
                "dry_run": False,
                "mock_mode": False,
                "confirm_live_trading": True,
                "enable_order_submission": True,
            }
        )

        with self.assertRaisesRegex(LiveSafetyError, "dry_run=false"):
            validate_live_order_submission_config(dry_run_config)
        with self.assertRaisesRegex(LiveSafetyError, "enable_order_submission"):
            validate_live_order_submission_config(missing_submission_flag)
        self.assertFalse(validate_live_order_submission_config(enabled_config).dry_run)

    def test_live_account_must_be_allowlisted(self) -> None:
        config = make_live_config()
        account = Account(
            account_id="other-account",
            timestamp=NOW,
            currency="USD",
            cash=100,
            equity=100,
            buying_power=100,
        )

        with self.assertRaises(LiveSafetyError):
            validate_live_account(config, account)

    def test_order_request_safety_enforces_symbol_and_size_caps(self) -> None:
        config = make_live_config()
        allowed = OrderRequest(
            client_order_id="live-ok",
            strategy_id="sma_live",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=2,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
        too_large = OrderRequest(
            client_order_id="live-too-large",
            strategy_id="sma_live",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=20,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )
        wrong_symbol = OrderRequest(
            client_order_id="live-wrong-symbol",
            strategy_id="sma_live",
            symbol="QQQ",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        self.assertTrue(validate_order_request_safety(config, allowed, price=100))
        with self.assertRaises(LiveSafetyError):
            validate_order_request_safety(config, too_large, price=100)
        with self.assertRaises(LiveSafetyError):
            validate_order_request_safety(config, wrong_symbol, price=100)

    def test_order_request_safety_enforces_fractional_execution_setting(self) -> None:
        config = make_live_config(execution={"allow_fractional": False})
        fractional = OrderRequest(
            client_order_id="live-fractional",
            strategy_id="sma_live",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=1.5,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        with self.assertRaises(LiveSafetyError):
            validate_order_request_safety(config, fractional, price=100)

    def test_order_request_safety_rejects_outside_market_session(self) -> None:
        config = make_live_config()
        outside_session = OrderRequest(
            client_order_id="live-outside-session",
            strategy_id="sma_live",
            symbol="SPY",
            timestamp="2026-01-05T13:00:00Z",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
        )

        with self.assertRaisesRegex(LiveSafetyError, "outside the configured market session"):
            validate_order_request_safety(config, outside_session, price=100)


if __name__ == "__main__":
    unittest.main()
