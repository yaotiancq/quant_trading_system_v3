"""In-memory Alpaca client for paper-engine dry runs and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class InMemoryAlpacaClient:
    """Tiny Alpaca-like client that never touches the network."""

    def __init__(
        self,
        *,
        account: dict[str, Any] | None = None,
        positions: list[dict[str, Any]] | None = None,
        fill_immediately: bool = False,
        fill_price: float = 100.0,
    ) -> None:
        self.account = account or {
            "id": "mock-alpaca-paper",
            "currency": "USD",
            "cash": "100000",
            "equity": "100000",
            "buying_power": "100000",
            "long_market_value": "0",
            "short_market_value": "0",
            "status": "ACTIVE",
            "created_at": _now_text(),
        }
        self.positions = list(positions or [])
        self.fill_immediately = fill_immediately
        self.fill_price = fill_price
        self.orders: dict[str, dict[str, Any]] = {}
        self.submitted_payloads: list[dict[str, Any]] = []
        self._order_counter = 0

    def get_account(self) -> dict[str, Any]:
        return dict(self.account)

    def list_positions(self) -> list[dict[str, Any]]:
        return [dict(position) for position in self.positions]

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._order_counter += 1
        order_id = f"mock-alpaca-order-{self._order_counter:06d}"
        now = _now_text()
        quantity = payload.get("qty")
        filled_quantity = quantity if self.fill_immediately and quantity is not None else "0"
        status = "filled" if self.fill_immediately and quantity is not None else "new"
        order = {
            "id": order_id,
            "client_order_id": payload.get("client_order_id") or order_id,
            "symbol": payload["symbol"],
            "side": payload["side"],
            "type": payload["type"],
            "time_in_force": payload["time_in_force"],
            "qty": quantity,
            "notional": payload.get("notional"),
            "filled_qty": filled_quantity,
            "filled_avg_price": str(self.fill_price) if status == "filled" else None,
            "status": status,
            "created_at": now,
            "submitted_at": now,
            "updated_at": now,
            "filled_at": now if status == "filled" else None,
            "limit_price": payload.get("limit_price"),
            "stop_price": payload.get("stop_price"),
        }
        self.orders[order_id] = order
        self.submitted_payloads.append(dict(payload))
        return dict(order)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        order = self.orders[order_id]
        if order["status"] not in {"filled", "canceled", "expired", "rejected"}:
            order["status"] = "canceled"
            order["updated_at"] = _now_text()
            order["canceled_at"] = order["updated_at"]
        return dict(order)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return dict(self.orders[order_id])

    def list_orders(
        self,
        *,
        status: str = "open",
        symbols: str | None = None,
        after: str | None = None,
        until: str | None = None,
        limit: int = 100,
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        selected = list(self.orders.values())
        if symbols:
            allowed = {symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()}
            selected = [order for order in selected if str(order["symbol"]).upper() in allowed]
        if status == "open":
            selected = [
                order
                for order in selected
                if order["status"] in {"new", "accepted", "partially_filled"}
            ]
        elif status == "closed":
            selected = [
                order
                for order in selected
                if order["status"] in {"filled", "canceled", "expired", "rejected"}
            ]
        selected = sorted(
            selected,
            key=lambda order: str(order.get("updated_at") or order.get("created_at")),
            reverse=direction != "asc",
        )
        return [dict(order) for order in selected[:limit]]

    def get_clock(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "timestamp": _now_text(now),
            "is_open": now.weekday() < 5,
            "next_open": _now_text(now),
            "next_close": _now_text(now),
        }

    def close(self) -> None:
        return None


def _now_text(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


__all__ = ["InMemoryAlpacaClient"]
