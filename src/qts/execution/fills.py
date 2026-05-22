"""Fill handling utilities for execution workflows."""

from __future__ import annotations

from qts.domain import Fill, Order

from .manager import OrderManager


class FillHandler:
    """Apply fill events to the execution order manager."""

    def __init__(self, order_manager: OrderManager) -> None:
        self.order_manager = order_manager

    def handle_fill(self, fill: Fill) -> Order:
        return self.order_manager.mark_filled(fill.order_id, fill)


__all__ = ["FillHandler"]
