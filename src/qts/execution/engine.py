"""Execution engine implementation."""

from __future__ import annotations

from collections.abc import Sequence

from qts.domain import Fill, Order, RiskDecision

from .fills import FillHandler
from .manager import OrderManager
from .orders import build_order_request
from .router import OrderRouter


class ExecutionEngine:
    """Convert approved risk decisions to orders and track updates."""

    def __init__(
        self,
        order_router: OrderRouter,
        *,
        order_manager: OrderManager | None = None,
        fill_handler: FillHandler | None = None,
    ) -> None:
        self.order_router = order_router
        self.order_manager = order_manager or OrderManager()
        self.fill_handler = fill_handler or FillHandler(self.order_manager)
        self._processed_fill_ids: set[str] = set()

    def submit(self, risk_decision: RiskDecision) -> Order:
        request = build_order_request(risk_decision)
        order = self.order_router.submit_order(request)
        self.order_manager.register_order(order)
        return order

    def submit_many(self, risk_decisions: Sequence[RiskDecision]) -> list[Order]:
        return [self.submit(decision) for decision in risk_decisions]

    def on_order_update(self, order: Order) -> None:
        self.order_manager.update_order(order)

    def on_fill(self, fill: Fill) -> Order:
        self._processed_fill_ids.add(fill.fill_id)
        return self.fill_handler.handle_fill(fill)

    def cancel_order(self, order_id: str) -> Order:
        order = self.order_router.cancel_order(order_id)
        self.order_manager.update_order(order)
        return order

    def poll_fills(self) -> list[Fill]:
        fills = self.order_router.poll_updates()
        for fill in fills:
            if (
                fill.fill_id not in self._processed_fill_ids
                and self.order_manager.get_order(fill.order_id) is not None
            ):
                self.on_fill(fill)
        return fills


__all__ = ["ExecutionEngine"]
