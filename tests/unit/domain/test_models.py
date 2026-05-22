from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.domain import (
    Bar,
    BarTimeframe,
    OrderRequest,
    OrderSide,
    OrderType,
    RiskDecision,
    RiskDecisionStatus,
    RuntimeMode,
    TimeInForce,
    TradeIntent,
)


UTC = timezone.utc


class DomainModelTests(unittest.TestCase):
    def test_bar_normalizes_symbol_timeframe_and_timestamp(self) -> None:
        bar = Bar(
            symbol="spy",
            timestamp=datetime(2026, 1, 5, 9, 31, tzinfo=UTC),
            timeframe="minute",
            open=500.10,
            high=500.35,
            low=499.95,
            close=500.20,
            volume=125000,
        )

        self.assertEqual(bar.symbol, "SPY")
        self.assertEqual(bar.timeframe, BarTimeframe.MINUTE)
        self.assertEqual(bar.timestamp.tzinfo, UTC)
        self.assertEqual(bar.to_dict()["timestamp"], "2026-01-05T09:31:00Z")

    def test_bar_rejects_naive_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            Bar(
                symbol="SPY",
                timestamp=datetime(2026, 1, 5, 9, 31),
                timeframe=BarTimeframe.MINUTE,
                open=1,
                high=1,
                low=1,
                close=1,
                volume=1,
            )

    def test_bar_rejects_invalid_ohlc(self) -> None:
        with self.assertRaises(ValueError):
            Bar(
                symbol="SPY",
                timestamp=datetime(2026, 1, 5, 9, 31, tzinfo=UTC),
                timeframe=BarTimeframe.MINUTE,
                open=10,
                high=9,
                low=8,
                close=10,
                volume=1,
            )

    def test_order_request_requires_quantity_or_notional(self) -> None:
        with self.assertRaises(ValueError):
            OrderRequest(
                client_order_id="coid-1",
                symbol="SPY",
                timestamp=datetime(2026, 1, 5, tzinfo=UTC),
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )

    def test_limit_trade_intent_requires_limit_price(self) -> None:
        with self.assertRaises(ValueError):
            TradeIntent(
                intent_id="intent-1",
                strategy_id="s1",
                symbol="SPY",
                timestamp=datetime(2026, 1, 5, tzinfo=UTC),
                side=OrderSide.BUY,
                quantity=10,
                order_type=OrderType.LIMIT,
            )

    def test_risk_decision_requires_approved_intent_when_approved(self) -> None:
        original = TradeIntent(
            intent_id="intent-1",
            strategy_id="s1",
            symbol="SPY",
            timestamp=datetime(2026, 1, 5, tzinfo=UTC),
            side=OrderSide.BUY,
            quantity=10,
        )

        with self.assertRaises(ValueError):
            RiskDecision(
                decision_id="risk-1",
                timestamp=datetime(2026, 1, 5, tzinfo=UTC),
                status=RiskDecisionStatus.APPROVED,
                original_intent=original,
            )

    def test_runtime_mode_serializes_to_value(self) -> None:
        self.assertEqual(RuntimeMode.BACKTEST.value, "BACKTEST")


if __name__ == "__main__":
    unittest.main()
