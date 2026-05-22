"""Order routing through the normalized brokerage interface."""

from __future__ import annotations

from datetime import datetime

from qts.brokers import Brokerage
from qts.domain import Fill, Order, OrderRequest


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


__all__ = ["OrderRouter"]
