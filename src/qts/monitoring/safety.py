"""Live-trading safety gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qts.calendar import build_market_session_service
from qts.core import LiveSafetyError
from qts.domain import Account, OrderRequest, RuntimeConfig, RuntimeMode, normalize_symbol


@dataclass(frozen=True)
class LiveSafetyPolicy:
    """Validated live safety settings."""

    live_enabled: bool
    dry_run: bool
    allowed_symbols: list[str]
    allowed_account_ids: list[str]
    max_order_notional: float | None
    max_order_quantity: float | None
    order_submission_enabled: bool = False
    automated_submission_enabled: bool = False
    automated_submission_kill_switch: bool = False


def validate_live_safety_config(config: RuntimeConfig) -> LiveSafetyPolicy:
    """Validate static live safety gates from runtime configuration."""
    if config.runtime_mode != RuntimeMode.LIVE:
        raise LiveSafetyError("LiveEngine requires LIVE runtime mode")
    build_market_session_service(config)

    safety = dict(config.broker.safety)
    if not _truthy(safety.get("live_enabled")):
        raise LiveSafetyError("live trading requires broker.safety.live_enabled=true")

    dry_run = _truthy(safety.get("dry_run")) or _truthy(safety.get("mock_mode"))
    if not dry_run and not _truthy(safety.get("confirm_live_trading")):
        raise LiveSafetyError(
            "non-dry-run live trading requires broker.safety.confirm_live_trading=true"
        )

    allowed_symbols = _normalized_list(safety.get("allowed_symbols"))
    if _truthy(safety.get("require_symbol_allowlist", True)):
        if not allowed_symbols:
            raise LiveSafetyError("live trading requires broker.safety.allowed_symbols")
        missing = sorted(symbol for symbol in config.symbols if symbol not in set(allowed_symbols))
        if missing:
            raise LiveSafetyError(
                "runtime symbols are not in the live symbol allowlist: " + ", ".join(missing)
            )

    max_order_notional = _optional_positive_float(safety.get("max_order_notional"))
    max_order_quantity = _optional_positive_float(safety.get("max_order_quantity"))
    if max_order_notional is None and max_order_quantity is None:
        raise LiveSafetyError(
            "live trading requires max_order_notional or max_order_quantity safety cap"
        )

    return LiveSafetyPolicy(
        live_enabled=True,
        dry_run=dry_run,
        allowed_symbols=allowed_symbols,
        allowed_account_ids=[str(item) for item in list(safety.get("allowed_account_ids") or [])],
        max_order_notional=max_order_notional,
        max_order_quantity=max_order_quantity,
        order_submission_enabled=_truthy(safety.get("enable_order_submission")),
        automated_submission_enabled=_truthy(safety.get("enable_automated_submission")),
        automated_submission_kill_switch=_truthy(safety.get("automated_submission_kill_switch")),
    )


def validate_live_order_submission_config(config: RuntimeConfig) -> LiveSafetyPolicy:
    """Validate explicit operator gates before a live order can be submitted."""
    policy = validate_live_safety_config(config)
    broker_type = config.broker.broker_type.lower()
    if policy.dry_run:
        raise LiveSafetyError("live order submission requires broker.safety.dry_run=false")
    if not policy.order_submission_enabled:
        raise LiveSafetyError(
            "live order submission requires broker.safety.enable_order_submission=true"
        )
    if config.broker.paper is not False:
        raise LiveSafetyError("live order submission requires broker.paper=false")
    if not broker_type.endswith("_live"):
        raise LiveSafetyError("live order submission requires a *_live broker_type")
    return policy


def validate_live_automated_submission_config(config: RuntimeConfig) -> LiveSafetyPolicy:
    """Validate explicit gates before strategy decisions may auto-submit."""
    policy = validate_live_order_submission_config(config)
    if not policy.automated_submission_enabled:
        raise LiveSafetyError(
            "automated live submission requires broker.safety.enable_automated_submission=true"
        )
    if policy.automated_submission_kill_switch:
        raise LiveSafetyError(
            "automated live submission blocked by broker.safety.automated_submission_kill_switch"
        )
    return policy


def validate_live_account(config: RuntimeConfig, account: Account) -> bool:
    """Validate broker account identity against the configured allowlist."""
    safety = dict(config.broker.safety)
    if not _truthy(safety.get("require_account_allowlist", True)):
        return True
    allowed = [str(item) for item in list(safety.get("allowed_account_ids") or [])]
    account_id = account.account_id or config.broker.account_id
    if not account_id:
        raise LiveSafetyError("live account allowlist is enabled but account_id is empty")
    if account_id not in allowed:
        raise LiveSafetyError(f"broker account is not in the live allowlist: {account_id}")
    return True


def validate_order_request_safety(
    config: RuntimeConfig,
    order_request: OrderRequest,
    *,
    price: float | None = None,
) -> bool:
    """Validate a normalized order request against live safety caps."""
    policy = validate_live_safety_config(config)
    session_service = build_market_session_service(config)
    if not session_service.is_tradable(order_request.timestamp):
        raise LiveSafetyError("order timestamp is outside the configured market session")
    symbol = normalize_symbol(order_request.symbol)
    if policy.allowed_symbols and symbol not in set(policy.allowed_symbols):
        raise LiveSafetyError(f"order symbol is not allowed for live trading: {symbol}")

    allow_fractional = bool(config.execution.get("allow_fractional", True))
    if (
        not allow_fractional
        and order_request.quantity is not None
        and abs(order_request.quantity - round(order_request.quantity)) > 1e-9
    ):
        raise LiveSafetyError("fractional quantities are disabled by execution config")

    if (
        policy.max_order_quantity is not None
        and order_request.quantity is not None
        and order_request.quantity > policy.max_order_quantity
    ):
        raise LiveSafetyError("order quantity exceeds live max_order_quantity")

    notional = order_request.notional
    if notional is None and order_request.quantity is not None and price is not None:
        notional = order_request.quantity * price
    if (
        policy.max_order_notional is not None
        and notional is not None
        and notional > policy.max_order_notional
    ):
        raise LiveSafetyError("order notional exceeds live max_order_notional")
    return True


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalized_list(value: Any) -> list[str]:
    return [normalize_symbol(item) for item in list(value or [])]


def _optional_positive_float(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if number <= 0:
        raise LiveSafetyError("live safety order caps must be positive")
    return number


__all__ = [
    "LiveSafetyPolicy",
    "validate_live_account",
    "validate_live_automated_submission_config",
    "validate_live_order_submission_config",
    "validate_live_safety_config",
    "validate_order_request_safety",
]
