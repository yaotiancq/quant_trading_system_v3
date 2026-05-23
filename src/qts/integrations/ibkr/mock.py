"""In-memory IBKR client for brokerage tests and dry runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class InMemoryIBKRClient:
    """Tiny IBKR-like client that never touches the network."""

    def __init__(
        self,
        *,
        account_id: str = "DU123456",
        account: dict[str, Any] | None = None,
        positions: list[dict[str, Any]] | None = None,
        fill_immediately: bool = False,
        fill_price: float = 100.0,
        require_order_reply: bool = False,
    ) -> None:
        self.account_id = account_id
        self.account = account or {
            "accountId": account_id,
            "currency": "USD",
            "totalcashvalue": {"amount": 100000, "currency": "USD"},
            "netliquidation": {"amount": 100000, "currency": "USD"},
            "buyingpower": {"amount": 100000, "currency": "USD"},
            "grosspositionvalue": {"amount": 0, "currency": "USD"},
        }
        self.positions = list(positions or [])
        self.fill_immediately = fill_immediately
        self.fill_price = fill_price
        self.require_order_reply = require_order_reply
        self.orders: dict[str, dict[str, Any]] = {}
        self.submitted_payloads: list[dict[str, Any]] = []
        self._order_counter = 0

    def get_account_summary(self, account_id: str) -> dict[str, Any]:
        return dict(self.account)

    def list_positions(self, account_id: str, *, page_id: int = 0) -> list[dict[str, Any]]:
        return [dict(position) for position in self.positions]

    def submit_order(self, account_id: str, payload: dict[str, Any]) -> Any:
        self.submitted_payloads.append(dict(payload))
        if self.require_order_reply:
            return [
                {
                    "id": "mock-ibkr-reply-1",
                    "message": ["Mock IBKR precautionary order reply required"],
                    "messageIds": ["o163"],
                    "isSuppressed": False,
                }
            ]

        self._order_counter += 1
        order_id = f"mock-ibkr-order-{self._order_counter:06d}"
        now = _now_text()
        filled_quantity = payload["quantity"] if self.fill_immediately else 0
        status = "Filled" if self.fill_immediately else "Submitted"
        order = {
            "order_id": order_id,
            "order_status": status,
            "acct": account_id,
            "conid": payload["conid"],
            "ticker": payload.get("ticker") or payload.get("symbol") or "SPY",
            "side": payload["side"],
            "orderType": payload["orderType"],
            "quantity": payload["quantity"],
            "filledQuantity": filled_quantity,
            "avgPrice": self.fill_price if self.fill_immediately else None,
            "price": payload.get("price"),
            "auxPrice": payload.get("auxPrice"),
            "cOID": payload.get("cOID") or order_id,
            "created_at": now,
            "updated_at": now,
        }
        self.orders[order_id] = order
        return {"order_id": order_id, "order_status": status}

    def cancel_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        order = self.orders[order_id]
        order["order_status"] = "Cancelled"
        order["updated_at"] = _now_text()
        return {"msg": "Request was submitted", "order_id": order_id, "account": account_id}

    def get_order_status(self, account_id: str, order_id: str) -> dict[str, Any]:
        return dict(self.orders[order_id])

    def list_orders(self, account_id: str, *, filters: str | None = None) -> list[dict[str, Any]]:
        return [dict(order) for order in self.orders.values() if order.get("acct") == account_id]

    def close(self) -> None:
        return None


def _now_text(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


__all__ = ["InMemoryIBKRClient"]
