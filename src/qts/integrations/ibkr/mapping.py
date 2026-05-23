"""Mapping between IBKR Web API payloads and normalized domain models."""

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
    TimeInForce,
    normalize_symbol,
    normalize_timestamp,
)


def order_request_to_ibkr_payload(
    order_request: OrderRequest,
    *,
    symbol_conids: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Convert a normalized order request into an IBKR order ticket."""
    conid = _resolve_conid(order_request, symbol_conids or {})
    if order_request.quantity is None:
        raise BrokerError("IBKR order submission requires quantity; notional orders are not supported")

    payload: dict[str, Any] = {
        "conid": conid,
        "side": order_request.side.value,
        "orderType": _ibkr_order_type(order_request.order_type),
        "quantity": order_request.quantity,
        "tif": _ibkr_tif(order_request.time_in_force),
        "cOID": order_request.client_order_id,
    }
    if order_request.limit_price is not None:
        payload["price"] = order_request.limit_price
    if order_request.stop_price is not None:
        payload["auxPrice"] = order_request.stop_price
    if "outsideRTH" in order_request.metadata:
        payload["outsideRTH"] = bool(order_request.metadata["outsideRTH"])
    if "outside_rth" in order_request.metadata:
        payload["outsideRTH"] = bool(order_request.metadata["outside_rth"])
    if "secType" in order_request.metadata:
        payload["secType"] = order_request.metadata["secType"]
    return payload


def ibkr_order_to_domain(
    payload: dict[str, Any],
    *,
    order_request: OrderRequest | None = None,
    account_id: str | None = None,
) -> Order:
    """Convert an IBKR order payload or acknowledgement into a normalized `Order`."""
    order_id = _text(
        payload.get("order_id")
        or payload.get("orderId")
        or payload.get("id")
        or (order_request.client_order_id if order_request else None),
        "order_id",
    )
    created_at = _timestamp(
        payload.get("created_at")
        or payload.get("createdTime")
        or payload.get("lastExecutionTime")
        or payload.get("time")
        or datetime.now(timezone.utc)
    )
    updated_at = _timestamp(
        payload.get("updated_at")
        or payload.get("lastExecutionTime")
        or payload.get("time")
        or created_at
    )
    side = _side(payload.get("side"), order_request)
    quantity = _optional_float(
        payload.get("quantity")
        or payload.get("totalSize")
        or payload.get("size")
        or (order_request.quantity if order_request else None)
    )
    filled_quantity = _optional_float(
        payload.get("filledQuantity")
        or payload.get("filled")
        or payload.get("filled_qty")
        or payload.get("filledQuantityDecimal")
    )
    if filled_quantity is None:
        filled_quantity = _filled_from_size_text(payload.get("sizeAndFills")) or 0.0
    remaining_quantity = (
        max(quantity - filled_quantity, 0.0) if quantity is not None else None
    )
    status = order_status_from_ibkr(str(payload.get("order_status") or payload.get("status") or ""))
    rejection_reason = _optional_text(payload.get("error") or payload.get("reject_reason"))
    if status == OrderStatus.REJECTED and not rejection_reason:
        rejection_reason = "ibkr_rejected"
    symbol = (
        payload.get("ticker")
        or payload.get("symbol")
        or payload.get("description1")
        or (order_request.symbol if order_request else "")
    )
    order_type = _order_type(payload.get("orderType") or payload.get("order_type"), order_request)
    return Order(
        order_id=order_id,
        client_order_id=_optional_text(payload.get("cOID"))
        or (order_request.client_order_id if order_request else order_id),
        symbol=normalize_symbol(str(symbol)),
        created_at=created_at,
        updated_at=updated_at,
        side=side,
        quantity=quantity,
        filled_quantity=filled_quantity,
        remaining_quantity=remaining_quantity,
        order_type=order_type,
        status=status,
        limit_price=_optional_float(payload.get("price") or payload.get("limit_price")),
        stop_price=_optional_float(payload.get("auxPrice") or payload.get("stop_price")),
        average_fill_price=_optional_float(
            payload.get("avgPrice") or payload.get("avg_fill_price") or payload.get("avgFillPrice")
        ),
        rejection_reason=rejection_reason,
        metadata={
            "account_id": account_id or payload.get("acct"),
            "ibkr_status": payload.get("order_status") or payload.get("status"),
            "conid": _optional_int(payload.get("conid") or payload.get("conidex")),
            "secType": payload.get("secType"),
            "raw_order_desc": payload.get("orderDesc"),
        },
    )


def ibkr_order_to_fill_delta(
    payload: dict[str, Any],
    previous_filled_quantity: float,
    *,
    order_request: OrderRequest | None = None,
    source: str = "ibkr",
) -> Fill | None:
    """Create a fill for newly observed filled quantity from an IBKR order payload."""
    current_filled_quantity = _optional_float(
        payload.get("filledQuantity")
        or payload.get("filled")
        or payload.get("filled_qty")
        or payload.get("filledQuantityDecimal")
    )
    if current_filled_quantity is None:
        current_filled_quantity = _filled_from_size_text(payload.get("sizeAndFills")) or 0.0
    delta = current_filled_quantity - previous_filled_quantity
    if delta <= 1e-9:
        return None
    price = _optional_float(payload.get("avgPrice") or payload.get("avgFillPrice"))
    if price is None:
        return None
    order = ibkr_order_to_domain(payload, order_request=order_request)
    suffix = _number_text(current_filled_quantity).replace(".", "_")
    return Fill(
        fill_id=f"ibkr-fill-{order.order_id}-{suffix}",
        order_id=order.order_id,
        client_order_id=order.client_order_id,
        symbol=order.symbol,
        timestamp=order.updated_at,
        side=order.side,
        quantity=delta,
        price=price,
        commission=0.0,
        liquidity_flag="ibkr",
        source=source,
    )


def ibkr_account_to_domain(payload: dict[str, Any], *, account_id: str | None = None) -> Account:
    """Convert an IBKR account summary payload into normalized account state."""
    resolved_account_id = account_id or _optional_text(payload.get("accountId") or payload.get("account"))
    currency = str(payload.get("currency") or _summary_currency(payload) or "USD")
    cash = _summary_value(payload, "totalcashvalue", "cash", "availablefunds")
    equity = _summary_value(payload, "netliquidation", "equity", "net_liquidation")
    buying_power = _summary_value(payload, "buyingpower", "buying_power", "availablefunds")
    gross_exposure = abs(_summary_value(payload, "grosspositionvalue", "gross_exposure", default=0.0))
    net_exposure = _summary_value(payload, "netexposure", "net_exposure", default=0.0)
    return Account(
        account_id=resolved_account_id,
        timestamp=datetime.now(timezone.utc),
        currency=currency,
        cash=cash,
        equity=equity if equity != 0 else cash,
        buying_power=max(buying_power, 0.0),
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        metadata={"source": "ibkr", "raw_keys": sorted(str(key) for key in payload)},
    )


def ibkr_position_to_domain(payload: dict[str, Any]) -> Position:
    """Convert an IBKR position payload into normalized position state."""
    quantity = _optional_float(payload.get("position") or payload.get("qty") or payload.get("quantity"))
    quantity = 0.0 if quantity is None else quantity
    market_price = _optional_float(payload.get("mktPrice") or payload.get("marketPrice"))
    average_cost = _optional_float(payload.get("avgCost") or payload.get("avg_cost"))
    symbol = (
        payload.get("ticker")
        or payload.get("symbol")
        or payload.get("contractDesc")
        or payload.get("description1")
        or ""
    )
    return Position(
        symbol=normalize_symbol(str(symbol).split()[0]),
        quantity=quantity,
        average_cost=average_cost or 0.0,
        market_price=market_price,
        market_value=abs(_optional_float(payload.get("mktValue") or payload.get("marketValue")) or 0.0),
        unrealized_pnl=_optional_float(payload.get("unrealizedPnl") or payload.get("unrealizedPNL")),
        updated_at=datetime.now(timezone.utc),
    )


def order_status_from_ibkr(status: str) -> OrderStatus:
    """Map IBKR order statuses into the normalized enum."""
    normalized = status.strip().lower().replace(" ", "")
    if normalized in {"submitted", "presubmitted", "pendingsubmit", "apipending"}:
        return OrderStatus.SUBMITTED
    if normalized in {"filled"}:
        return OrderStatus.FILLED
    if normalized in {"partiallyfilled", "partfilled"}:
        return OrderStatus.PARTIALLY_FILLED
    if normalized in {"cancelled", "canceled", "pendingcancel"}:
        return OrderStatus.CANCELED
    if normalized in {"inactive", "rejected"}:
        return OrderStatus.REJECTED
    if normalized in {"expired"}:
        return OrderStatus.EXPIRED
    if normalized in {"", "unknown"}:
        return OrderStatus.ACCEPTED
    return OrderStatus.FAILED


def is_order_reply_required(response: Any) -> bool:
    """Return whether an IBKR order response requires explicit reply confirmation."""
    items = response if isinstance(response, list) else [response]
    for item in items:
        if isinstance(item, dict) and item.get("id") and item.get("message"):
            return True
    return False


def first_order_ack(response: Any) -> dict[str, Any]:
    """Extract the first order acknowledgement from an IBKR order response."""
    items = response if isinstance(response, list) else [response]
    for item in items:
        if isinstance(item, dict) and (item.get("order_id") or item.get("orderId")):
            return dict(item)
    raise BrokerError("IBKR order response did not include an order acknowledgement")


def _resolve_conid(order_request: OrderRequest, symbol_conids: dict[str, int]) -> int:
    value = (
        order_request.metadata.get("ibkr_conid")
        or order_request.metadata.get("conid")
        or symbol_conids.get(order_request.symbol)
    )
    if value is None:
        raise BrokerError(f"IBKR order submission requires conid for {order_request.symbol}")
    return int(value)


def _ibkr_order_type(order_type: OrderType) -> str:
    if order_type == OrderType.MARKET:
        return "MKT"
    if order_type == OrderType.LIMIT:
        return "LMT"
    if order_type == OrderType.STOP:
        return "STP"
    if order_type == OrderType.STOP_LIMIT:
        return "STP LMT"
    raise BrokerError(f"unsupported IBKR order type: {order_type}")


def _ibkr_tif(time_in_force: TimeInForce) -> str:
    if time_in_force in {TimeInForce.DAY, TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK}:
        return time_in_force.value
    raise BrokerError(f"unsupported IBKR time in force: {time_in_force}")


def _order_type(value: Any, order_request: OrderRequest | None) -> OrderType:
    if value is None and order_request is not None:
        return order_request.order_type
    normalized = str(value or "").strip().upper().replace(" ", "_")
    mapping = {
        "MKT": OrderType.MARKET,
        "MARKET": OrderType.MARKET,
        "LMT": OrderType.LIMIT,
        "LIMIT": OrderType.LIMIT,
        "STP": OrderType.STOP,
        "STOP": OrderType.STOP,
        "STP_LMT": OrderType.STOP_LIMIT,
        "STOP_LIMIT": OrderType.STOP_LIMIT,
    }
    return mapping.get(normalized, OrderType.MARKET)


def _side(value: Any, order_request: OrderRequest | None) -> OrderSide:
    if value is None and order_request is not None:
        return order_request.side
    return OrderSide(str(value or "").strip().upper())


def _summary_value(payload: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if isinstance(value, dict):
            value = value.get("amount") or value.get("value")
        parsed = _optional_float(value)
        if parsed is not None:
            return parsed
    return default


def _summary_currency(payload: dict[str, Any]) -> str | None:
    for value in payload.values():
        if isinstance(value, dict) and value.get("currency"):
            return str(value["currency"])
    return None


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return normalize_timestamp(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    return normalize_timestamp(str(value)) if value else datetime.now(timezone.utc)


def _filled_from_size_text(value: Any) -> float | None:
    if not value:
        return None
    text = str(value)
    if "/" not in text:
        return None
    _size, filled = text.split("/", 1)
    return _optional_float(filled)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BrokerError(f"expected numeric IBKR value, got {value!r}") from exc


def _optional_int(value: Any) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise BrokerError(f"missing required IBKR field: {field_name}")
    return text


def _number_text(value: float | int) -> str:
    return f"{float(value):g}"


__all__ = [
    "first_order_ack",
    "ibkr_account_to_domain",
    "ibkr_order_to_domain",
    "ibkr_order_to_fill_delta",
    "ibkr_position_to_domain",
    "is_order_reply_required",
    "order_request_to_ibkr_payload",
    "order_status_from_ibkr",
]
