from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.domain import (
    Fill,
    OrderSide,
    PortfolioSnapshot,
    Position,
    RiskConfig,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
    TradeIntent,
)
from qts.risk import CooldownRule, RiskEngine
from qts.risk.rules import projected_symbol_exposure


UTC = timezone.utc
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


def snapshot(
    *,
    cash: float = 10000.0,
    equity: float = 10000.0,
    gross_exposure: float = 0.0,
    positions_value: float | None = None,
    realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0,
    buying_power: float | None = None,
    positions: list[Position] | None = None,
) -> PortfolioSnapshot:
    metadata = {}
    if buying_power is not None:
        metadata["buying_power"] = buying_power
    return PortfolioSnapshot(
        timestamp=NOW,
        cash=cash,
        equity=equity,
        positions_value=gross_exposure if positions_value is None else positions_value,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        gross_exposure=gross_exposure,
        net_exposure=gross_exposure,
        positions=list(positions or []),
        metadata=metadata,
    )


def risk_config(**overrides: object) -> RiskConfig:
    values = {
        "sizing_method": "fixed_notional",
        "sizing_parameters": {"notional_per_trade": 1000},
    }
    values.update(overrides)
    return RiskConfig(**values)


def signal(
    timestamp: datetime = NOW,
    symbol: str = "SPY",
    strategy_id: str = "strategy-1",
) -> Signal:
    return Signal(
        signal_id=f"sig-{symbol}-{timestamp.strftime('%H%M%S')}",
        strategy_id=strategy_id,
        symbol=symbol,
        timestamp=timestamp,
        direction=SignalDirection.BUY,
        reason="test_signal",
    )


class RiskEngineTests(unittest.TestCase):
    def test_engine_sizes_signal_and_returns_modified_decision(self) -> None:
        engine = RiskEngine(risk_config())

        decision = engine.evaluate(signal(), snapshot(), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.MODIFIED)
        self.assertIsNotNone(decision.approved_intent)
        self.assertEqual(decision.approved_intent.notional, 1000)
        self.assertIn("sizing_applied", decision.reasons)

    def test_engine_approves_presized_trade_intent(self) -> None:
        engine = RiskEngine(risk_config(sizing_parameters={"notional_per_trade": 5000}))
        intent = TradeIntent(
            intent_id="intent-1",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            notional=1000,
        )

        decision = engine.evaluate(intent, snapshot(), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.APPROVED)
        self.assertEqual(decision.approved_intent.notional, 1000)
        self.assertIn("already_sized", decision.reasons)

    def test_symbol_blocklist_rejects_intent(self) -> None:
        engine = RiskEngine(risk_config(blocked_symbols=["SPY"]))

        decision = engine.evaluate(signal(), snapshot(), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("symbol_blocked", decision.reasons)
        self.assertIsNone(decision.approved_intent)

    def test_position_notional_limit_modifies_intent(self) -> None:
        engine = RiskEngine(
            risk_config(
                sizing_parameters={"notional_per_trade": 5000},
                max_position_notional=3000,
            )
        )

        decision = engine.evaluate(signal(), snapshot(cash=10000), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.MODIFIED)
        self.assertEqual(decision.approved_intent.notional, 3000)
        self.assertIn("position_notional_reduced_to_limit", decision.reasons)

    def test_gross_exposure_limit_rejects_projected_excess(self) -> None:
        engine = RiskEngine(
            risk_config(
                sizing_parameters={"notional_per_trade": 2000},
                max_gross_exposure=10000,
            )
        )

        decision = engine.evaluate(signal(), snapshot(gross_exposure=9000), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("gross_exposure_limit_exceeded", decision.reasons)

    def test_risk_reducing_sell_is_not_rejected_as_new_gross_exposure(self) -> None:
        engine = RiskEngine(
            risk_config(
                max_position_notional=1400,
                max_gross_exposure=1400,
                max_symbol_weight=0.14,
            )
        )
        intent = TradeIntent(
            intent_id="reduce-long",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.SELL,
            quantity=5,
        )
        current_position = Position(
            symbol="SPY",
            quantity=20,
            average_cost=100,
            market_price=100,
            updated_at=NOW,
        )

        decision = engine.evaluate(
            intent,
            snapshot(
                equity=10000,
                gross_exposure=2000,
                positions_value=2000,
                positions=[current_position],
            ),
            {"timestamp": NOW, "price": 100},
        )

        self.assertEqual(decision.status, RiskDecisionStatus.APPROVED)
        self.assertIn("position_exposure_reduced", decision.reasons)
        self.assertIn("gross_exposure_reduced", decision.reasons)

    def test_buy_to_cover_short_reduces_projected_exposure(self) -> None:
        engine = RiskEngine(risk_config(max_position_notional=1200, max_gross_exposure=1200))
        intent = TradeIntent(
            intent_id="cover-short",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            quantity=5,
        )
        current_position = Position(
            symbol="SPY",
            quantity=-20,
            average_cost=100,
            market_price=100,
            updated_at=NOW,
        )

        decision = engine.evaluate(
            intent,
            snapshot(gross_exposure=2000, positions_value=2000, positions=[current_position]),
            {"timestamp": NOW, "price": 100},
        )

        self.assertEqual(decision.status, RiskDecisionStatus.APPROVED)
        self.assertIn("position_exposure_reduced", decision.reasons)
        self.assertIn("gross_exposure_reduced", decision.reasons)

    def test_buying_power_rule_uses_snapshot_metadata_when_present(self) -> None:
        engine = RiskEngine(risk_config(sizing_parameters={"notional_per_trade": 5000}))

        decision = engine.evaluate(signal(), snapshot(cash=10000, buying_power=4000), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("insufficient_buying_power", decision.reasons)

    def test_trading_session_rule_rejects_outside_session(self) -> None:
        outside_session = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)
        engine = RiskEngine(
            risk_config(
                session_rules={
                    "enabled": True,
                    "market_open": "14:30",
                    "market_close": "21:00",
                    "weekdays": [0, 1, 2, 3, 4],
                }
            )
        )

        decision = engine.evaluate(
            signal(timestamp=outside_session),
            snapshot(),
            {"timestamp": outside_session},
        )

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("outside_trading_session", decision.reasons)

    def test_trading_session_rule_allows_open_and_rejects_close_boundary(self) -> None:
        engine = RiskEngine(
            risk_config(
                session_rules={
                    "enabled": True,
                    "market_open": "14:30",
                    "market_close": "21:00",
                    "weekdays": [0, 1, 2, 3, 4],
                }
            )
        )
        open_time = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
        close_time = datetime(2026, 1, 5, 21, 0, tzinfo=UTC)

        open_decision = engine.evaluate(signal(timestamp=open_time), snapshot(), {"timestamp": open_time})
        close_decision = engine.evaluate(signal(timestamp=close_time), snapshot(), {"timestamp": close_time})

        self.assertNotEqual(open_decision.status, RiskDecisionStatus.REJECTED)
        self.assertEqual(close_decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("outside_trading_session", close_decision.reasons)

    def test_cooldown_rule_rejects_same_strategy_symbol_follow_up(self) -> None:
        engine = RiskEngine(risk_config(cooldown_seconds=60))
        first_decision = engine.evaluate(signal(), snapshot(), {"timestamp": NOW})
        follow_up_time = NOW + timedelta(seconds=30)

        decision = engine.evaluate(
            signal(timestamp=follow_up_time),
            snapshot(),
            {"timestamp": follow_up_time},
        )

        self.assertNotEqual(first_decision.status, RiskDecisionStatus.REJECTED)
        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("cooldown_active", decision.reasons)

    def test_cooldown_rule_is_scoped_by_strategy_and_symbol(self) -> None:
        engine = RiskEngine(risk_config(cooldown_seconds=60))
        engine.evaluate(signal(strategy_id="strategy-a"), snapshot(), {"timestamp": NOW})
        follow_up_time = NOW + timedelta(seconds=30)

        decision = engine.evaluate(
            signal(timestamp=follow_up_time, strategy_id="strategy-b"),
            snapshot(),
            {"timestamp": follow_up_time},
        )

        self.assertNotEqual(decision.status, RiskDecisionStatus.REJECTED)

    def test_cooldown_fill_fallback_strategy_key_is_deterministic(self) -> None:
        rule = CooldownRule()
        rule.record_fill(
            Fill(
                fill_id="fill-1",
                order_id="order-1",
                symbol="SPY",
                timestamp=NOW,
                side=OrderSide.BUY,
                quantity=10,
                price=100,
                commission=0,
                source="unit_test",
            )
        )
        follow_up_time = NOW + timedelta(seconds=30)
        intent = TradeIntent(
            intent_id="unknown-strategy-intent",
            strategy_id="__unknown_strategy__",
            symbol="SPY",
            timestamp=follow_up_time,
            side=OrderSide.BUY,
            quantity=1,
        )

        result = rule.evaluate(
            intent,
            snapshot(),
            {"timestamp": follow_up_time},
            risk_config(cooldown_seconds=60),
        )

        self.assertEqual(result.status, RiskDecisionStatus.REJECTED)
        self.assertEqual(result.reason, "cooldown_active")

    def test_daily_loss_rejects_when_realized_limit_reached(self) -> None:
        engine = RiskEngine(risk_config(daily_loss_limit=500))

        decision = engine.evaluate(signal(), snapshot(realized_pnl=-600), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("daily_loss_limit_reached", decision.reasons)

    def test_daily_loss_rejects_when_unrealized_limit_reached(self) -> None:
        engine = RiskEngine(risk_config(daily_loss_limit=500))

        decision = engine.evaluate(signal(), snapshot(unrealized_pnl=-600), {"timestamp": NOW})

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("daily_loss_limit_reached", decision.reasons)

    def test_daily_loss_includes_unrealized_pnl(self) -> None:
        engine = RiskEngine(risk_config(daily_loss_limit=500))

        decision = engine.evaluate(
            signal(),
            snapshot(realized_pnl=-100, unrealized_pnl=-450),
            {"timestamp": NOW},
        )

        self.assertEqual(decision.status, RiskDecisionStatus.REJECTED)
        self.assertIn("daily_loss_limit_reached", decision.reasons)

    def test_daily_loss_allows_losses_within_limit(self) -> None:
        engine = RiskEngine(risk_config(daily_loss_limit=500))

        decision = engine.evaluate(
            signal(),
            snapshot(realized_pnl=-100, unrealized_pnl=-200),
            {"timestamp": NOW},
        )

        self.assertNotEqual(decision.status, RiskDecisionStatus.REJECTED)

    def test_buy_notional_without_price_increases_projected_exposure(self) -> None:
        intent = TradeIntent(
            intent_id="buy-notional",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.BUY,
            notional=500,
        )
        current_position = Position(
            symbol="SPY",
            quantity=20,
            average_cost=100,
            market_value=2000,
            updated_at=NOW,
        )

        exposure = projected_symbol_exposure(
            intent,
            snapshot(gross_exposure=2000, positions_value=2000, positions=[current_position]),
            {"timestamp": NOW},
        )

        self.assertEqual(exposure, (2000, 2500))

    def test_sell_notional_without_price_reduces_projected_exposure(self) -> None:
        intent = TradeIntent(
            intent_id="sell-notional",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.SELL,
            notional=500,
        )
        current_position = Position(
            symbol="SPY",
            quantity=20,
            average_cost=100,
            market_value=2000,
            updated_at=NOW,
        )

        exposure = projected_symbol_exposure(
            intent,
            snapshot(gross_exposure=2000, positions_value=2000, positions=[current_position]),
            {"timestamp": NOW},
        )

        self.assertEqual(exposure, (2000, 1500))

    def test_sell_notional_with_price_reduces_projected_exposure(self) -> None:
        intent = TradeIntent(
            intent_id="sell-notional-price",
            strategy_id="strategy-1",
            symbol="SPY",
            timestamp=NOW,
            side=OrderSide.SELL,
            notional=500,
        )
        current_position = Position(
            symbol="SPY",
            quantity=20,
            average_cost=100,
            market_value=2000,
            updated_at=NOW,
        )

        exposure = projected_symbol_exposure(
            intent,
            snapshot(gross_exposure=2000, positions_value=2000, positions=[current_position]),
            {"timestamp": NOW, "price": 100},
        )

        self.assertEqual(exposure, (2000, 1500))


if __name__ == "__main__":
    unittest.main()
