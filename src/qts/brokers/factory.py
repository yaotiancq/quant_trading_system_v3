"""Brokerage factory helpers."""

from __future__ import annotations

from typing import Any

from qts.core import ConfigurationError
from qts.domain import BrokerConfig, RuntimeMode

from .alpaca import AlpacaBrokerage
from .backtest import BacktestBrokerage
from .ibkr import IBKRBrokerage
from .interfaces import Brokerage


SUPPORTED_BROKER_TYPES = frozenset(
    {
        "alpaca_live",
        "alpaca_paper",
        "backtest",
        "ibkr_paper",
    }
)


def create_brokerage(
    config: BrokerConfig,
    *,
    runtime_mode: RuntimeMode | str | None = None,
    **kwargs: Any,
) -> Brokerage:
    """Create the configured brokerage without connecting it."""
    broker_type = _broker_type(config)
    mode = _runtime_mode_value(runtime_mode)
    _validate_mode_support(config, broker_type, mode)

    if broker_type in {"alpaca_paper", "alpaca_live"}:
        return AlpacaBrokerage(config, **kwargs)
    if broker_type == "ibkr_paper":
        return IBKRBrokerage(config, **kwargs)
    if broker_type == "backtest":
        return BacktestBrokerage(config, **kwargs)
    raise _unsupported_broker_error(broker_type, mode)


def create_backtest_brokerage(
    config: BrokerConfig,
    *,
    starting_cash: float,
    currency: str,
    account_id: str | None = None,
) -> Brokerage:
    """Create a backtest brokerage while preserving simulation model settings."""
    broker_type = _broker_type(config)
    if broker_type != "backtest":
        raise _unsupported_broker_error(broker_type, RuntimeMode.BACKTEST.value)
    return BacktestBrokerage(
        config,
        starting_cash=starting_cash,
        currency=currency,
        account_id=account_id or config.account_id or "backtest",
        fill_policy=config.fill_policy,
        commission_model=config.commission_model,
        slippage_model=config.slippage_model,
    )


def _validate_mode_support(
    config: BrokerConfig,
    broker_type: str,
    runtime_mode: str | None,
) -> None:
    if runtime_mode is None:
        if broker_type not in SUPPORTED_BROKER_TYPES:
            raise _unsupported_broker_error(broker_type, runtime_mode)
        return
    supported_by_mode = {
        RuntimeMode.BACKTEST.value: {"backtest"},
        RuntimeMode.PAPER.value: {"alpaca_paper", "ibkr_paper"},
        RuntimeMode.LIVE.value: {"alpaca_live"},
    }
    supported = supported_by_mode.get(runtime_mode)
    if supported is None or broker_type not in supported:
        raise _unsupported_broker_error(broker_type, runtime_mode)
    if runtime_mode == RuntimeMode.PAPER.value and config.paper is False:
        raise ConfigurationError("PAPER runtime requires a paper broker configuration")


def _broker_type(config: BrokerConfig) -> str:
    return str(config.broker_type).strip().lower()


def _runtime_mode_value(runtime_mode: RuntimeMode | str | None) -> str | None:
    if runtime_mode is None:
        return None
    return str(runtime_mode.value if isinstance(runtime_mode, RuntimeMode) else runtime_mode).upper()


def _unsupported_broker_error(broker_type: str, runtime_mode: str | None) -> ConfigurationError:
    mode_text = f" for runtime mode {runtime_mode}" if runtime_mode else ""
    supported = ", ".join(sorted(SUPPORTED_BROKER_TYPES))
    return ConfigurationError(
        f"unsupported broker type {broker_type!r}{mode_text}; "
        f"supported broker types: {supported}"
    )


__all__ = [
    "SUPPORTED_BROKER_TYPES",
    "create_backtest_brokerage",
    "create_brokerage",
]
