"""Normalized IBKR paper brokerage adapter."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime
from typing import Any

from qts.core import BrokerError, LiveSafetyError
from qts.domain import (
    Account,
    BrokerConfig,
    Fill,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    normalize_symbol,
    normalize_timestamp,
)
from qts.integrations.ibkr import (
    IBKRAPIError,
    IBKRClient,
    InMemoryIBKRClient,
    create_ibkr_web_api_client,
    first_order_ack,
    ibkr_account_to_domain,
    ibkr_order_to_domain,
    ibkr_order_to_fill_delta,
    ibkr_position_to_domain,
    is_order_reply_required,
    order_request_to_ibkr_payload,
)


class IBKRBrokerage:
    """Brokerage implementation for IBKR paper trading through Web API."""

    def __init__(
        self,
        broker_config: BrokerConfig | None = None,
        *,
        client: IBKRClient | None = None,
        env_values: dict[str, str] | None = None,
    ) -> None:
        self.broker_config = broker_config or BrokerConfig(
            broker_type="ibkr_paper",
            account_id="DU123456",
            paper=True,
            credential_env_keys={"access_token": "IBKR_ACCESS_TOKEN"},
        )
        self.client = client
        self.env_values = dict(env_values or os.environ)
        self._connected = False
        self._orders: dict[str, Order] = {}
        self._order_requests_by_order_id: dict[str, OrderRequest] = {}
        self._filled_quantities_by_order_id: dict[str, float] = {}

    def connect(self, broker_config: BrokerConfig | None = None) -> None:
        if broker_config is not None:
            self.broker_config = broker_config
        self._ensure_paper_only()
        account_id = self._account_id()
        if self.client is None:
            if _mock_mode(self.broker_config):
                self.client = InMemoryIBKRClient(account_id=account_id)
            else:
                self.client = create_ibkr_web_api_client(
                    self.broker_config,
                    env_values=self.env_values,
                )
        self._connected = True

    def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
        self._connected = False

    def submit_order(self, order_request: OrderRequest) -> Order:
        self._require_connected()
        account_id = self._account_id()
        payload = order_request_to_ibkr_payload(
            order_request,
            symbol_conids=self._symbol_conids(),
        )
        response = self._call("submit_order", self.client.submit_order, account_id, payload)
        if is_order_reply_required(response):
            raise BrokerError(
                "IBKR order requires manual reply confirmation; automatic confirmation is disabled"
            )
        order = ibkr_order_to_domain(
            first_order_ack(response),
            order_request=order_request,
            account_id=account_id,
        )
        metadata = dict(order.metadata)
        metadata.update(
            {
                "strategy_id": order_request.strategy_id,
                "requested_notional": order_request.notional,
                "time_in_force": order_request.time_in_force.value,
            }
        )
        order = replace(order, metadata=metadata)
        self._cache_order(order, order_request=order_request)
        self._filled_quantities_by_order_id.setdefault(order.order_id, 0.0)
        return order

    def cancel_order(self, order_id: str) -> Order:
        self._require_connected()
        account_id = self._account_id()
        response = self._call("cancel_order", self.client.cancel_order, account_id, order_id)
        if response.get("order_status") or response.get("status"):
            order = ibkr_order_to_domain(
                response,
                order_request=self._order_requests_by_order_id.get(order_id),
                account_id=account_id,
            )
        else:
            order = self.get_order(order_id)
            if order is None:
                cached = self._orders.get(order_id)
                if cached is None:
                    raise BrokerError(f"unknown IBKR order after cancel: {order_id}")
                order = replace(cached, status=OrderStatus.CANCELED)
        return self._cache_order(order)

    def get_order(self, order_id: str) -> Order | None:
        self._require_connected()
        account_id = self._account_id()
        try:
            response = self.client.get_order_status(account_id, order_id)
        except IBKRAPIError as exc:
            if exc.status_code == 404:
                return None
            raise BrokerError(f"ibkr get_order failed: {exc}") from exc
        except Exception as exc:
            raise BrokerError(f"ibkr get_order failed: {exc}") from exc
        order = ibkr_order_to_domain(
            response,
            order_request=self._order_requests_by_order_id.get(order_id),
            account_id=account_id,
        )
        return self._cache_order(order)

    def list_orders(
        self,
        status: OrderStatus | str | None = None,
        symbol: str | None = None,
    ) -> list[Order]:
        self._require_connected()
        account_id = self._account_id()
        response = self._call("list_orders", self.client.list_orders, account_id)
        orders = [
            ibkr_order_to_domain(
                payload,
                order_request=self._order_requests_by_order_id.get(
                    str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or "")
                ),
                account_id=account_id,
            )
            for payload in response
        ]
        domain_status = _domain_status(status)
        if domain_status is not None:
            orders = [order for order in orders if order.status == domain_status]
        if symbol is not None:
            normalized_symbol = normalize_symbol(symbol)
            orders = [order for order in orders if order.symbol == normalized_symbol]
        return [self._cache_order(order) for order in orders]

    def get_account(self) -> Account:
        self._require_connected()
        account_id = self._account_id()
        response = self._call("get_account_summary", self.client.get_account_summary, account_id)
        return ibkr_account_to_domain(response, account_id=account_id)

    def get_positions(self) -> list[Position]:
        self._require_connected()
        account_id = self._account_id()
        response = self._call("list_positions", self.client.list_positions, account_id)
        return [ibkr_position_to_domain(item) for item in response]

    def poll_fills(self, since: datetime | None = None) -> list[Fill]:
        self._require_connected()
        account_id = self._account_id()
        response = self._call("list_orders", self.client.list_orders, account_id)
        fills: list[Fill] = []
        for payload in response:
            order_id = str(payload.get("order_id") or payload.get("orderId") or payload.get("id") or "")
            order_request = self._order_requests_by_order_id.get(order_id)
            order = ibkr_order_to_domain(payload, order_request=order_request, account_id=account_id)
            previous_quantity = self._filled_quantities_by_order_id.get(order.order_id, 0.0)
            fill = ibkr_order_to_fill_delta(
                payload,
                previous_quantity,
                order_request=order_request,
                source="ibkr_paper",
            )
            self._cache_order(order)
            self._filled_quantities_by_order_id[order.order_id] = order.filled_quantity
            if fill is None:
                continue
            if since is not None and fill.timestamp < normalize_timestamp(since):
                continue
            fills.append(fill)
        return fills

    def is_market_open(self, timestamp: datetime) -> bool:
        self._require_connected()
        return normalize_timestamp(timestamp).weekday() < 5

    def _ensure_paper_only(self) -> None:
        broker_type = self.broker_config.broker_type.lower()
        if self.broker_config.paper is False or broker_type == "ibkr_live":
            raise LiveSafetyError("IBKR live brokerage is not enabled; use ibkr_paper")

    def _account_id(self) -> str:
        account_id = self.broker_config.account_id or self.broker_config.safety.get("account_id")
        if not account_id:
            raise BrokerError("IBKR brokerage requires broker.account_id")
        return str(account_id)

    def _symbol_conids(self) -> dict[str, int]:
        raw = self.broker_config.safety.get("symbol_conids") or {}
        if not isinstance(raw, dict):
            raise BrokerError("IBKR safety.symbol_conids must be a mapping")
        return {normalize_symbol(str(symbol)): int(conid) for symbol, conid in raw.items()}

    def _require_connected(self) -> None:
        if not self._connected or self.client is None:
            raise BrokerError("IBKRBrokerage is not connected")

    def _call(self, name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except IBKRAPIError as exc:
            raise BrokerError(f"ibkr {name} failed: {exc}") from exc
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"ibkr {name} failed: {exc}") from exc

    def _cache_order(self, order: Order, *, order_request: OrderRequest | None = None) -> Order:
        cached = self._orders.get(order.order_id)
        if cached is not None:
            metadata = dict(cached.metadata)
            metadata.update(order.metadata)
            order = replace(order, metadata=metadata)
        self._orders[order.order_id] = order
        if order_request is not None:
            self._order_requests_by_order_id[order.order_id] = order_request
        return order


def _mock_mode(broker_config: BrokerConfig) -> bool:
    safety = dict(broker_config.safety)
    return bool(safety.get("mock_mode") or safety.get("dry_run"))


def _domain_status(status: OrderStatus | str | None) -> OrderStatus | None:
    if status is None:
        return None
    if isinstance(status, str) and status.lower() in {"open", "closed", "all"}:
        return None
    return OrderStatus(status) if isinstance(status, str) else status


__all__ = ["IBKRBrokerage"]
