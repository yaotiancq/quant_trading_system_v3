"""Order request construction for approved risk decisions."""

from __future__ import annotations

from typing import Any

from qts.core import ExecutionError
from qts.domain import OrderRequest, RiskDecision, RiskDecisionStatus, normalize_timestamp


def build_order_request(
    risk_decision: RiskDecision,
    *,
    timestamp: Any | None = None,
    client_order_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    allow_fractional: bool = True,
) -> OrderRequest:
    """Convert an approved risk decision into a broker-ready order request."""
    if risk_decision.status == RiskDecisionStatus.REJECTED:
        raise ExecutionError("cannot build order request from rejected risk decision")
    if risk_decision.approved_intent is None:
        raise ExecutionError("risk decision has no approved intent")

    intent = risk_decision.approved_intent
    _validate_quantity_notional(intent.quantity, intent.notional)
    _validate_fractional_quantity(intent.quantity, allow_fractional=allow_fractional)
    if intent.notional is not None and not allow_fractional:
        raise ExecutionError(
            "notional orders require execution.allow_fractional=true; "
            "use quantity-based sizing for whole-share execution"
        )
    request_metadata: dict[str, Any] = {
        "risk_decision_id": risk_decision.decision_id,
        "risk_status": risk_decision.status.value,
        "intent_id": intent.intent_id,
        "source_signal_id": intent.source_signal_id,
    }
    request_metadata.update(intent.metadata)
    request_metadata.update(metadata or {})
    request_metadata = {
        key: value for key, value in request_metadata.items() if value is not None
    }

    return OrderRequest(
        client_order_id=client_order_id or f"coid-{risk_decision.decision_id}",
        strategy_id=intent.strategy_id,
        symbol=intent.symbol,
        timestamp=normalize_timestamp(timestamp or risk_decision.timestamp),
        side=intent.side,
        quantity=intent.quantity,
        notional=intent.notional,
        order_type=intent.order_type,
        limit_price=intent.limit_price,
        stop_price=intent.stop_price,
        time_in_force=intent.time_in_force,
        metadata=request_metadata,
    )


def _validate_fractional_quantity(quantity: float | None, *, allow_fractional: bool) -> None:
    if allow_fractional or quantity is None:
        return
    if abs(quantity - round(quantity)) > 1e-9:
        raise ExecutionError("fractional quantities are disabled by execution config")


def _validate_quantity_notional(quantity: float | None, notional: float | None) -> None:
    if quantity is not None and notional is not None:
        raise ExecutionError("provide either quantity or notional, not both")
    if quantity is None and notional is None:
        raise ExecutionError("quantity or notional is required")


__all__ = ["build_order_request"]
