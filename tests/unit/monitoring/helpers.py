from __future__ import annotations

from datetime import datetime, timezone

from qts.domain import BrokerConfig, RuntimeConfig, StrategyConfig


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_live_config(
    *,
    safety: dict[str, object] | None = None,
    symbols: list[str] | None = None,
    account_id: str = "acct-1",
    execution: dict[str, object] | None = None,
) -> RuntimeConfig:
    merged_safety = {
        "live_enabled": True,
        "dry_run": True,
        "mock_mode": True,
        "require_account_allowlist": True,
        "allowed_account_ids": [account_id],
        "require_symbol_allowlist": True,
        "allowed_symbols": symbols or ["SPY"],
        "max_order_notional": 1000,
        "max_order_quantity": 10,
    }
    merged_safety.update(dict(safety or {}))
    selected_symbols = symbols or ["SPY"]
    return RuntimeConfig(
        run_id="live-test",
        runtime_mode="LIVE",
        symbols=selected_symbols,
        timeframe="MINUTE",
        market_data={"provider": "external_events"},
        broker=BrokerConfig(
            broker_type="alpaca_live",
            account_id=account_id,
            paper=False,
            safety=merged_safety,
        ),
        strategies=[
            StrategyConfig(
                strategy_id="sma_live",
                strategy_type="sma_crossover",
                symbols=selected_symbols,
                parameters={"fast_window": 2, "slow_window": 3},
            )
        ],
        risk={
            "sizing_method": "fixed_notional",
            "sizing_parameters": {"notional_per_trade": 100},
        },
        portfolio={"currency": "USD"},
        execution={"allow_fractional": False, **dict(execution or {})},
        monitoring={"enabled": True},
    )
