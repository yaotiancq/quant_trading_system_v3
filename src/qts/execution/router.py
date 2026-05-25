"""Order routing through the normalized brokerage interface."""

from __future__ import annotations

from datetime import datetime

from qts.brokers.interfaces import Brokerage
from qts.domain import BrokerEvent, Fill, Order, OrderRequest

from .events import broker_events_from_poll


class OrderRouter:
    """Thin router that delegates only to a configured brokerage."""

    def __init__(self, brokerage: Brokerage) -> None:
        self.brokerage = brokerage

    def submit_order(self, order_request: OrderRequest) -> Order:
        return self.brokerage.submit_order(order_request)

    def cancel_order(self, order_id: str) -> Order:
        return self.brokerage.cancel_order(order_id)

    def get_order(self, order_id: str) -> Order | None:
        return self.brokerage.get_order(order_id)

    def poll_updates(self, since: datetime | None = None) -> list[Fill]:
        return self.brokerage.poll_fills(since)

    def poll_events(
        self,
        since: datetime | None = None,
        *,
        include_order_updates: bool = True,
    ) -> list[BrokerEvent]:
        orders = self.brokerage.list_orders(status="all") if include_order_updates else []
        fills = self.brokerage.poll_fills(since)
        broker_name = type(self.brokerage).__name__
        return broker_events_from_poll(orders=orders, fills=fills, source=f"{broker_name}.poll")


__all__ = ["OrderRouter"]
