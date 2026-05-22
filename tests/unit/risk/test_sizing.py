from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.core import RiskError
from qts.domain import (
    OrderSide,
    PortfolioSnapshot,
    Position,
    RiskConfig,
    Signal,
    SignalDirection,
    TargetPosition,
)
from qts.risk import DefaultPositionSizer, trade_intent_from_signal, trade_intent_from_target_position


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def snapshot(equity: float = 10000.0, cash: float = 10000.0) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=NOW,
        cash=cash,
        equity=equity,
        positions_value=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        gross_exposure=0.0,
        net_exposure=0.0,
    )


def buy_signal() -> Signal:
    return Signal(
        signal_id="sig-1",
        strategy_id="strategy-1",
        symbol="SPY",
        timestamp=NOW,
        direction=SignalDirection.BUY,
        confidence=0.8,
        reason="test_signal",
    )


class PositionSizingTests(unittest.TestCase):
    def test_fixed_notional_sizer_converts_signal_to_sized_trade_intent(self) -> None:
        result = DefaultPositionSizer().size(
            buy_signal(),
            snapshot(),
            {},
            RiskConfig(
                sizing_method="fixed_notional",
                sizing_parameters={"notional_per_trade": 2500},
            ),
        )

        self.assertTrue(result.modified)
        self.assertEqual(result.intent.side, OrderSide.BUY)
        self.assertEqual(result.intent.notional, 2500)
        self.assertEqual(result.intent.source_signal_id, "sig-1")

    def test_percent_equity_sizer_uses_portfolio_equity(self) -> None:
        result = DefaultPositionSizer().size(
            buy_signal(),
            snapshot(equity=20000),
            {},
            RiskConfig(
                sizing_method="percent_equity",
                sizing_parameters={"percent": 0.1},
            ),
        )

        self.assertEqual(result.intent.notional, 2000)

    def test_hold_signal_is_not_actionable(self) -> None:
        signal = Signal(
            signal_id="hold-1",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            direction=SignalDirection.HOLD,
        )

        with self.assertRaises(RiskError):
            trade_intent_from_signal(signal)

    def test_target_quantity_uses_current_position_delta(self) -> None:
        portfolio = snapshot()
        portfolio.positions.append(
            Position(
                symbol="SPY",
                quantity=25,
                average_cost=100,
                market_price=100,
                updated_at=NOW,
            )
        )
        target = TargetPosition(
            target_id="target-1",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            target_quantity=50,
        )

        intent = trade_intent_from_target_position(target, portfolio)

        self.assertEqual(intent.side, OrderSide.BUY)
        self.assertEqual(intent.quantity, 25)


if __name__ == "__main__":
    unittest.main()
