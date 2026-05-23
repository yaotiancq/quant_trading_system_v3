from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qts.brokers.alpaca import AlpacaBrokerage
from qts.core import ConfigurationError, load_runtime_config
from qts.domain import Bar, BarTimeframe, PortfolioSnapshot, Signal, SignalDirection
from qts.engines import PaperTradingEngine
from qts.strategies import BaseStrategy


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs" / "paper_alpaca.yaml"
NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


class BuyOnceStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__()
        self.fired = False
        self.fills_seen = 0

    def on_data(
        self,
        market_event: Bar,
        features: Any,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self._validate_symbol(market_event.symbol)
        if self.fired:
            return []
        self.fired = True
        return [
            Signal(
                signal_id="sig-buy-once",
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=SignalDirection.BUY,
                confidence=1.0,
                reason="test_buy_once",
            )
        ]

    def on_fill(self, fill) -> None:  # type: ignore[no-untyped-def]
        self.fills_seen += 1


class FillOnPollClient:
    def __init__(self) -> None:
        self.submitted_payloads: list[dict[str, object]] = []
        self.order: dict[str, object] | None = None

    def get_account(self) -> dict[str, object]:
        return {
            "id": "acct-1",
            "currency": "USD",
            "cash": "100000",
            "equity": "100000",
            "buying_power": "100000",
            "long_market_value": "0",
            "short_market_value": "0",
            "created_at": "2026-01-05T14:29:00Z",
        }

    def list_positions(self) -> list[dict[str, object]]:
        return []

    def submit_order(self, payload: dict[str, object]) -> dict[str, object]:
        self.submitted_payloads.append(dict(payload))
        self.order = {
            "id": "alpaca-order-1",
            "client_order_id": payload["client_order_id"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "type": payload["type"],
            "time_in_force": payload["time_in_force"],
            "qty": payload["qty"],
            "filled_qty": "0",
            "filled_avg_price": None,
            "status": "new",
            "created_at": "2026-01-05T14:30:00Z",
            "submitted_at": "2026-01-05T14:30:00Z",
            "updated_at": "2026-01-05T14:30:00Z",
        }
        return dict(self.order)

    def cancel_order(self, order_id: str) -> dict[str, object]:
        assert self.order is not None
        self.order["status"] = "canceled"
        return dict(self.order)

    def get_order(self, order_id: str) -> dict[str, object]:
        assert self.order is not None
        return dict(self.order)

    def list_orders(self, **kwargs: object) -> list[dict[str, object]]:
        assert self.order is not None
        self.order.update(
            {
                "status": "filled",
                "filled_qty": self.order["qty"],
                "filled_avg_price": "100",
                "filled_at": "2026-01-05T14:31:00Z",
                "updated_at": "2026-01-05T14:31:00Z",
            }
        )
        return [dict(self.order)]

    def get_clock(self) -> dict[str, object]:
        return {"is_open": True, "timestamp": "2026-01-05T14:30:00Z"}

    def close(self) -> None:
        return None


def load_paper_config(**overrides: object):
    base_overrides: dict[str, object] = {
        "broker": {"safety": {"mock_mode": True}},
        "risk": {
            "sizing_method": "fixed_quantity",
            "sizing_parameters": {"quantity": 10},
        },
    }
    base_overrides.update(overrides)
    return load_runtime_config(CONFIG, env_path=None, overrides=base_overrides)


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


class PaperTradingEngineIntegrationTests(unittest.TestCase):
    def test_paper_engine_initializes_without_credentials_in_mock_mode(self) -> None:
        config = load_paper_config()

        status = PaperTradingEngine(config).start(max_events=0)

        self.assertTrue(status["initialized"])
        self.assertTrue(status["healthy"])
        self.assertTrue(status["mock_mode"])
        self.assertEqual(status["market_data_provider"], "external_events")
        self.assertEqual(status["reconciliation"]["status"], "matched")

    def test_paper_engine_rejects_unimplemented_market_data_provider(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_paper_config(market_data={"provider": "alpaca"})

    def test_paper_engine_rejects_unsupported_broker_type(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_paper_config(broker={"broker_type": "backtest", "paper": True})

    def test_paper_engine_uses_shared_execution_path_for_market_event(self) -> None:
        config = load_paper_config()
        client = FillOnPollClient()
        brokerage = AlpacaBrokerage(config.broker, client=client)
        strategy = BuyOnceStrategy()
        engine = PaperTradingEngine(config, brokerage=brokerage, strategies=[strategy])
        engine.initialize()

        orders = engine.on_market_event(make_bar())

        self.assertEqual(len(orders), 1)
        self.assertEqual(client.submitted_payloads[0]["qty"], "10")
        self.assertEqual(engine.portfolio.get_position("SPY").quantity, 10)
        self.assertEqual(strategy.fills_seen, 1)


if __name__ == "__main__":
    unittest.main()
