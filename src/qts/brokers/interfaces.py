"""Normalized brokerage interface contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from qts.domain import Account, BrokerConfig, Fill, Order, OrderRequest, Position


class Brokerage(Protocol):
    """Brokerage contract shared by backtest and future real brokers."""

    def connect(self, broker_config: BrokerConfig | None = None) -> None:
        """Initialize broker connection or simulation state."""

    def disconnect(self) -> None:
        """Close broker connection or simulation state."""

    def submit_order(self, order_request: OrderRequest) -> Order:
        """Submit a normalized order request."""

    def cancel_order(self, order_id: str) -> Order:
        """Cancel an order if it is still open."""

    def get_order(self, order_id: str) -> Order | None:
        """Return a normalized order by ID."""

    def list_orders(
        self,
        status: str | None = None,
        symbol: str | None = None,
    ) -> list[Order]:
        """List normalized broker orders."""

    def get_account(self) -> Account:
        """Return broker-side account state."""

    def get_positions(self) -> list[Position]:
        """Return broker-side positions."""

    def poll_fills(self, since: datetime | None = None) -> list[Fill]:
        """Return fill updates since an optional timestamp."""

    def is_market_open(self, timestamp: datetime) -> bool:
        """Return whether the broker considers the market open."""


__all__ = ["Brokerage"]
