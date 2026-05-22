from __future__ import annotations

import unittest

from qts.domain import Account
from qts.monitoring import BrokerReconciliationCheck, HealthStatus
from qts.portfolio import DefaultPortfolio

from .helpers import NOW


class FakeBrokerage:
    def __init__(self, account: Account) -> None:
        self.account = account

    def get_account(self) -> Account:
        return self.account

    def get_positions(self):
        return []


class ReconciliationMonitoringTests(unittest.TestCase):
    def test_reconciliation_check_reports_match(self) -> None:
        portfolio = DefaultPortfolio(100, account_id="acct-1", timestamp=NOW)
        broker = FakeBrokerage(
            Account(
                account_id="acct-1",
                timestamp=NOW,
                currency="USD",
                cash=100,
                equity=100,
                buying_power=100,
            )
        )

        result = BrokerReconciliationCheck(portfolio, broker).run()

        self.assertEqual(result.status, HealthStatus.OK)
        self.assertTrue(result.details["matched"])

    def test_reconciliation_check_reports_mismatch(self) -> None:
        portfolio = DefaultPortfolio(100, account_id="acct-1", timestamp=NOW)
        broker = FakeBrokerage(
            Account(
                account_id="acct-1",
                timestamp=NOW,
                currency="USD",
                cash=90,
                equity=90,
                buying_power=90,
            )
        )

        result = BrokerReconciliationCheck(portfolio, broker).run()

        self.assertEqual(result.status, HealthStatus.CRITICAL)
        self.assertFalse(result.details["matched"])
        self.assertEqual(result.details["cash_difference"], 10)


if __name__ == "__main__":
    unittest.main()
