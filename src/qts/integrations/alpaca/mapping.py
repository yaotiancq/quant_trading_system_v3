"""Mapping between Alpaca payloads and normalized domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from qts.core import BrokerError
from qts.domain import (
    Account,
    Fill,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    normalize_symbol,
    normalize_timestamp,
)


ALPACA_OPEN_QUERY_STATUSES = {
    OrderStatus.NEW,
    OrderStatus.ACCEPTED,
    OrderStatus.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED,
}
ALPACA_CLOSED_QUERY_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
    OrderStatus.FAILED,
}


def order_request_to_alpaca_payload(order_request: OrderRequest) -> dict[str, Any]:
    """Convert a normalized order request into Alpaca's order body."""
    payload: dict[str, Any] = {
        "symbol": order_request.symbol,
        "side": order_request.side.value.lower(),
        "type": _alpaca_order_type(order_request.order_type),
        "time_in_force": order_request.time_in_force.value.lower(),
        "client_order_id": order_request.client_order_id,
    }
    if order_request.quantity is not None:
        payload["qty"] = _number_text(order_request.quantity)
    if order_request.notional is not None:
        payload["notional"] = _number_text(order_request.notional)
    if order_request.limit_price is not None:
        payload["limit_price"] = _number_text(order_request.limit_price)
    if order_request.stop_price is not None:
        payload["stop_price"] = _number_text(order_request.stop_price)
    if "extended_hours" in order_request.metadata:
        payload["extended_hours"] = bool(order_request.metadata["extended_hours"])
    return payload


def alpaca_order_to_domain(payload: dict[str, Any]) -> Order:
    """Convert an Alpaca order payload into a normalized `Order`."""
    status = order_status_from_alpaca(str(payload.get("status", "")))
    quantity = _optional_float(payload.get("qty"))
    filled_quantity = _float(payload.get("filled_qty"), default=0.0)
    remaining_quantity = max(quantity - filled_quantity, 0.0) if quantity is not None else None
    rejection_reason = _optional_text(
        payload.get("reject_reason")
        or payload.get("rejected_reason")
        or payload.get("failure_reason")
    )
    if status == OrderStatus.REJECTED and not rejection_reason:
        rejection_reason = "alpaca_rejected"
    order_id = _required_text(payload.get("id"), "id")
    created_at = _first_timestamp(
        payload,
        "created_at",
        "submitted_at",
        "updated_at",
        "filled_at",
        "canceled_at",
        "expired_at",
    )
    updated_at = _optional_timestamp(
        payload.get("updated_at")
        or payload.get("filled_at")
        or payload.get("canceled_at")
        or payload.get("expired_at")
    )
    return Order(
        order_id=order_id,
        client_order_id=str(payload.get("client_order_id") or order_id),
        symbol=normalize_symbol(str(payload.get("symbol", ""))),
        created_at=created_at,
        updated_at=updated_at,
        side=_order_side(payload.get("side")),
        quantity=quantity,
        filled_quantity=filled_quantity,
        remaining_quantity=remaining_quantity,
        order_type=_order_type(payload.get("type")),
        status=status,
        limit_price=_optional_float(payload.get("limit_price")),
        stop_price=_optional_float(payload.get("stop_price")),
        average_fill_price=_optional_float(payload.get("filled_avg_price")),
        rejection_reason=rejection_reason,
        metadata={
            "alpaca_status": payload.get("status"),
            "asset_id": payload.get("asset_id"),
            "notional": _optional_float(payload.get("notional")),
            "submitted_at": payload.get("submitted_at"),
            "time_in_force": str(payload.get("time_in_force", "")).upper() or None,
        },
    )


def alpaca_order_to_fill_delta(
    payload: dict[str, Any],
    previous_filled_quantity: float,
    *,
    source: str = "alpaca_paper",
) -> Fill | None:
    """Create a fill for the newly observed filled quantity on an Alpaca order."""
    current_filled_quantity = _float(payload.get("filled_qty"), default=0.0)
    delta = current_filled_quantity - previous_filled_quantity
    if delta <= 1e-9:
        return None
    price = _optional_float(payload.get("filled_avg_price"))
    if price is None:
        return None
    order_id = _required_text(payload.get("id"), "id")
    fill_suffix = _number_text(current_filled_quantity).replace(".", "_")
    return Fill(
        fill_id=f"alpaca-fill-{order_id}-{fill_suffix}",
        order_id=order_id,
        client_order_id=_optional_text(payload.get("client_order_id")),
        symbol=normalize_symbol(str(payload.get("symbol", ""))),
        timestamp=_first_timestamp(
            payload,
            "filled_at",
            "updated_at",
            "submitted_at",
            "created_at",
        ),
        side=_order_side(payload.get("side")),
        quantity=delta,
        price=price,
        commission=0.0,
        liquidity_flag="alpaca",
        source=source,
    )


def alpaca_account_to_domain(payload: dict[str, Any]) -> Account:
    """Convert Alpaca account payload into normalized account state."""
    timestamp = _optional_timestamp(payload.get("created_at")) or datetime.now(timezone.utc)
    return Account(
        account_id=_optional_text(payload.get("id") or payload.get("account_number")),
        timestamp=timestamp,
        currency=str(payload.get("currency") or "USD"),
        cash=_float(payload.get("cash"), default=0.0),
        equity=_float(payload.get("equity"), default=0.0),
        buying_power=max(_float(payload.get("buying_power"), default=0.0), 0.0),
        gross_exposure=abs(_float(payload.get("long_market_value"), default=0.0))
        + abs(_float(payload.get("short_market_value"), default=0.0)),
        net_exposure=_float(payload.get("long_market_value"), default=0.0)
        + _float(payload.get("short_market_value"), default=0.0),
        metadata={
            "status": payload.get("status"),
            "trading_blocked": payload.get("trading_blocked"),
            "transfers_blocked": payload.get("transfers_blocked"),
            "account_blocked": payload.get("account_blocked"),
            "pattern_day_trader": payload.get("pattern_day_trader"),
        },
    )


def alpaca_position_to_domain(payload: dict[str, Any]) -> Position:
    """Convert an Alpaca open position payload into a normalized position."""
    quantity = _float(payload.get("qty"), default=0.0)
    market_price = _optional_float(payload.get("current_price"))
    average_cost = _float(payload.get("avg_entry_price"), default=0.0)
    return Position(
        symbol=normalize_symbol(str(payload.get("symbol", ""))),
        quantity=quantity,
        average_cost=average_cost,
        market_price=market_price,
        market_value=abs(_float(payload.get("market_value"), default=quantity * (market_price or 0.0))),
        unrealized_pnl=_optional_float(payload.get("unrealized_pl")),
        updated_at=datetime.now(timezone.utc),
    )


def order_status_from_alpaca(status: str) -> OrderStatus:
    """Map Alpaca order statuses into the normalized enum."""
    normalized = status.strip().lower()
    if normalized in {"accepted", "accepted_for_bidding"}:
        return OrderStatus.ACCEPTED
    if normalized in {"new", "pending_new", "calculated"}:
        return OrderStatus.SUBMITTED
    if normalized == "partially_filled":
        return OrderStatus.PARTIALLY_FILLED
    if normalized == "filled":
        return OrderStatus.FILLED
    if normalized in {"canceled", "cancelled", "pending_cancel", "done_for_day", "replaced"}:
        return OrderStatus.CANCELED
    if normalized == "expired":
        return OrderStatus.EXPIRED
    if normalized in {"rejected", "stopped", "suspended"}:
        return OrderStatus.REJECTED
    return OrderStatus.FAILED


def alpaca_query_status(status: OrderStatus | str | None) -> str:
    """Choose Alpaca's broad list-order status query value."""
    if status is None:
        return "open"
    if isinstance(status, str) and status.lower() in {"open", "closed", "all"}:
        return status.lower()
    normalized = OrderStatus(status) if isinstance(status, str) else status
    if normalized in ALPACA_OPEN_QUERY_STATUSES:
        return "open"
    if normalized in ALPACA_CLOSED_QUERY_STATUSES:
        return "closed"
    return "all"


def should_filter_domain_status(status: OrderStatus | str | None) -> OrderStatus | None:
    if status is None:
        return None
    if isinstance(status, str) and status.lower() in {"open", "closed", "all"}:
        return None
    return OrderStatus(status) if isinstance(status, str) else status


def _alpaca_order_type(order_type: OrderType) -> str:
    return order_type.value.lower().replace("_", "_")


def _order_type(value: Any) -> OrderType:
    normalized = str(value or "").strip().upper()
    if normalized == "STOP_LIMIT":
        return OrderType.STOP_LIMIT
    return OrderType(normalized)


def _order_side(value: Any) -> OrderSide:
    return OrderSide(str(value or "").strip().upper())


def _first_timestamp(payload: dict[str, Any], *keys: str) -> datetime:
    for key in keys:
        value = payload.get(key)
        if value:
            return normalize_timestamp(str(value))
    return datetime.now(timezone.utc)


def _optional_timestamp(value: Any) -> datetime | None:
    return normalize_timestamp(str(value)) if value else None


def _number_text(value: float | int) -> str:
    return f"{float(value):g}"


def _float(value: Any, *, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BrokerError(f"expected numeric Alpaca value, got {value!r}") from exc


def _required_text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise BrokerError(f"missing required Alpaca field: {field_name}")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "alpaca_account_to_domain",
    "alpaca_order_to_domain",
    "alpaca_order_to_fill_delta",
    "alpaca_position_to_domain",
    "alpaca_query_status",
    "order_request_to_alpaca_payload",
    "order_status_from_alpaca",
    "should_filter_domain_status",
]
