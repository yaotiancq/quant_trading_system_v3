from __future__ import annotations

import unittest

from qts.brokers.alpaca import AlpacaBrokerage
from qts.brokers.backtest import BacktestBrokerage
from qts.brokers.factory import create_backtest_brokerage, create_brokerage
from qts.brokers.ibkr import IBKRBrokerage
from qts.core import ConfigurationError
from qts.domain import BrokerConfig, RuntimeMode


class BrokerageFactoryTests(unittest.TestCase):
    def test_create_brokerage_creates_alpaca_brokerage(self) -> None:
        broker = create_brokerage(
            BrokerConfig(broker_type="alpaca_paper", paper=True),
            runtime_mode=RuntimeMode.PAPER,
        )

        self.assertIsInstance(broker, AlpacaBrokerage)
        self.assertFalse(broker._connected)

    def test_create_brokerage_creates_ibkr_brokerage(self) -> None:
        broker = create_brokerage(
            BrokerConfig(
                broker_type="ibkr_paper",
                account_id="DU123456",
                paper=True,
            ),
            runtime_mode=RuntimeMode.PAPER,
        )

        self.assertIsInstance(broker, IBKRBrokerage)
        self.assertFalse(broker._connected)

    def test_create_backtest_brokerage_preserves_simulation_models(self) -> None:
        config = BrokerConfig(
            broker_type="backtest",
            fill_policy="next_bar_close",
            commission_model={"type": "per_share", "amount": 0.01},
            slippage_model={"type": "bps", "bps": 5},
        )

        broker = create_backtest_brokerage(
            config,
            starting_cash=25000,
            currency="USD",
            account_id="bt-account",
        )

        self.assertIsInstance(broker, BacktestBrokerage)
        self.assertFalse(broker._connected)
        self.assertEqual(broker.fill_policy, "next_bar_close")
        self.assertEqual(broker.commission_model, {"type": "per_share", "amount": 0.01})
        self.assertEqual(broker.slippage_model, {"type": "bps", "bps": 5})
        self.assertEqual(broker.get_account().account_id, "bt-account")
        self.assertEqual(broker.get_account().cash, 25000)

    def test_unsupported_broker_type_raises_configuration_error(self) -> None:
        with self.assertRaisesRegex(
            ConfigurationError,
            "unsupported broker type 'unknown'.*runtime mode PAPER.*alpaca_paper.*ibkr_paper",
        ):
            create_brokerage(
                BrokerConfig(broker_type="unknown", paper=True),
                runtime_mode=RuntimeMode.PAPER,
            )

    def test_runtime_mode_restrictions_fail_fast(self) -> None:
        with self.assertRaisesRegex(
            ConfigurationError,
            "unsupported broker type 'alpaca_live'.*runtime mode PAPER",
        ):
            create_brokerage(
                BrokerConfig(broker_type="alpaca_live", paper=False),
                runtime_mode=RuntimeMode.PAPER,
            )


if __name__ == "__main__":
    unittest.main()
