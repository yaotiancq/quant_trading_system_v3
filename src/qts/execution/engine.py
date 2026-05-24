"""Execution engine implementation."""

from __future__ import annotations

from collections.abc import Sequence

from datetime import datetime

from qts.core import ExecutionError
from qts.domain import BrokerEvent, BrokerEventType, Fill, Order, RiskDecision

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
        allow_fractional: bool = True,
    ) -> None:
        self.order_router = order_router
        self.order_manager = order_manager or OrderManager()
        self.fill_handler = fill_handler or FillHandler(self.order_manager)
        self.allow_fractional = bool(allow_fractional)
        self._processed_fill_ids: set[str] = set()
        self._processed_broker_event_ids: set[str] = set()

    def submit(self, risk_decision: RiskDecision) -> Order:
        request = build_order_request(
            risk_decision,
            allow_fractional=self.allow_fractional,
        )
        order = self.order_router.submit_order(request)
        self.order_manager.register_order(order)
        return order

    def submit_many(self, risk_decisions: Sequence[RiskDecision]) -> list[Order]:
        return [self.submit(decision) for decision in risk_decisions]

    def on_order_update(self, order: Order) -> None:
        self.order_manager.apply_order_update(order)

    def on_fill(self, fill: Fill) -> Order:
        if fill.fill_id in self._processed_fill_ids:
            order = self.order_manager.get_order(fill.order_id)
            if order is None:
                raise ExecutionError(f"unknown order for duplicate fill: {fill.order_id}")
            return order
        self._processed_fill_ids.add(fill.fill_id)
        return self.fill_handler.handle_fill(fill)

    def on_broker_event(self, event: BrokerEvent) -> None:
        """Apply one normalized broker event with idempotent event handling."""
        if event.event_id in self._processed_broker_event_ids:
            return
        self._processed_broker_event_ids.add(event.event_id)
        if event.event_type == BrokerEventType.ORDER_UPDATE and event.order is not None:
            self.on_order_update(event.order)
            return
        if event.event_type == BrokerEventType.FILL and event.fill is not None:
            self.on_fill(event.fill)
            return

    def cancel_order(self, order_id: str) -> Order:
        order = self.order_router.cancel_order(order_id)
        self.order_manager.update_order(order)
        return order

    def poll_fills(self) -> list[Fill]:
        fills = self.order_router.poll_updates()
        for fill in fills:
            if self.order_manager.get_order(fill.order_id) is not None:
                self.on_fill(fill)
        return fills

    def poll_broker_events(self, since: datetime | None = None) -> list[BrokerEvent]:
        events = self.order_router.poll_events(since=since)
        for event in events:
            if event.event_type != BrokerEventType.FILL or (
                event.fill is not None
                and self.order_manager.get_order(event.fill.order_id) is not None
            ):
                self.on_broker_event(event)
        return events


__all__ = ["ExecutionEngine"]
