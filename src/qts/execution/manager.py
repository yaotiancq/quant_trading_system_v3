"""Normalized order lifecycle tracking."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from qts.core import ExecutionError
from qts.domain import Fill, Order, OrderStatus, normalize_symbol, normalize_timestamp


OPEN_ORDER_STATUSES = {
    OrderStatus.NEW,
    OrderStatus.ACCEPTED,
    OrderStatus.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED,
}


class OrderManager:
    """Track internal order state independent of any concrete broker."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def register_order(self, order: Order) -> None:
        if order.order_id in self._orders:
            raise ExecutionError(f"order already registered: {order.order_id}")
        self._orders[order.order_id] = order

    def update_order(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def list_open_orders(self, symbol: str | None = None) -> list[Order]:
        normalized_symbol = normalize_symbol(symbol) if symbol else None
        orders = [
            order
            for order in self._orders.values()
            if order.status in OPEN_ORDER_STATUSES
            and (normalized_symbol is None or order.symbol == normalized_symbol)
        ]
        return sorted(orders, key=lambda order: (order.created_at, order.order_id))

    def mark_filled(self, order_id: str, fill: Fill) -> Order:
        order = self._require_order(order_id)
        previous_filled = order.filled_quantity
        filled_quantity = previous_filled + fill.quantity
        target_quantity = order.quantity or filled_quantity
        remaining_quantity = max(target_quantity - filled_quantity, 0.0)
        previous_notional = (order.average_fill_price or 0.0) * previous_filled
        average_fill_price = (previous_notional + fill.price * fill.quantity) / filled_quantity
        status = (
            OrderStatus.FILLED
            if remaining_quantity <= 1e-9
            else OrderStatus.PARTIALLY_FILLED
        )
        updated = replace(
            order,
            quantity=target_quantity,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_fill_price=average_fill_price,
            status=status,
            updated_at=fill.timestamp,
        )
        self.update_order(updated)
        return updated

    def mark_canceled(self, order_id: str, timestamp: datetime | None = None) -> Order:
        order = self._require_order(order_id)
        if order.status not in OPEN_ORDER_STATUSES:
            return order
        updated_at = normalize_timestamp(timestamp or order.updated_at or order.created_at)
        updated = replace(order, status=OrderStatus.CANCELED, updated_at=updated_at)
        self.update_order(updated)
        return updated

    def _require_order(self, order_id: str) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise ExecutionError(f"unknown order: {order_id}")
        return order


__all__ = ["OPEN_ORDER_STATUSES", "OrderManager"]
