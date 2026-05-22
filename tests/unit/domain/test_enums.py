from __future__ import annotations

import unittest

from qts.domain import (
    BarTimeframe,
    DataAdjustment,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
    RuntimeMode,
    SignalDirection,
    TimeInForce,
)


class EnumTests(unittest.TestCase):
    def test_enum_values_are_stable(self) -> None:
        self.assertEqual([item.value for item in RuntimeMode], ["BACKTEST", "PAPER", "LIVE"])
        self.assertEqual([item.value for item in BarTimeframe], ["SECOND", "MINUTE", "HOUR", "DAY"])
        self.assertEqual(
            [item.value for item in SignalDirection],
            ["BUY", "SELL", "SHORT", "COVER", "HOLD", "EXIT"],
        )
        self.assertEqual([item.value for item in OrderSide], ["BUY", "SELL"])
        self.assertEqual([item.value for item in OrderType], ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"])
        self.assertEqual(
            [item.value for item in OrderStatus],
            [
                "NEW",
                "ACCEPTED",
                "REJECTED",
                "SUBMITTED",
                "PARTIALLY_FILLED",
                "FILLED",
                "CANCELED",
                "EXPIRED",
                "FAILED",
            ],
        )
        self.assertEqual([item.value for item in TimeInForce], ["DAY", "GTC", "IOC", "FOK"])
        self.assertEqual([item.value for item in RiskDecisionStatus], ["APPROVED", "REJECTED", "MODIFIED"])
        self.assertEqual(
            [item.value for item in DataAdjustment],
            ["RAW", "SPLIT_ADJUSTED", "DIVIDEND_ADJUSTED", "TOTAL_RETURN"],
        )


if __name__ == "__main__":
    unittest.main()
