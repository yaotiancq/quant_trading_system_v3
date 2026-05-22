"""Normalized Alpaca paper brokerage adapter."""

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
from qts.integrations.alpaca import (
    AlpacaAPIError,
    AlpacaClient,
    InMemoryAlpacaClient,
    alpaca_account_to_domain,
    alpaca_order_to_domain,
    alpaca_order_to_fill_delta,
    alpaca_position_to_domain,
    alpaca_query_status,
    create_alpaca_trading_client,
    order_request_to_alpaca_payload,
    should_filter_domain_status,
)


class AlpacaBrokerage:
    """Brokerage implementation for Alpaca paper trading."""

    def __init__(
        self,
        broker_config: BrokerConfig | None = None,
        *,
        client: AlpacaClient | None = None,
        env_values: dict[str, str] | None = None,
    ) -> None:
        self.broker_config = broker_config or BrokerConfig(
            broker_type="alpaca_paper",
            paper=True,
            credential_env_keys={
                "api_key_id": "ALPACA_API_KEY_ID",
                "secret_key": "ALPACA_SECRET_KEY",
            },
        )
        self.client = client
        self.env_values = dict(env_values or os.environ)
        self._connected = False
        self._orders: dict[str, Order] = {}
        self._filled_quantities_by_order_id: dict[str, float] = {}

    def connect(self, broker_config: BrokerConfig | None = None) -> None:
        if broker_config is not None:
            self.broker_config = broker_config
        self._ensure_paper_only()
        if self.client is None:
            if _mock_mode(self.broker_config):
                self.client = InMemoryAlpacaClient()
            else:
                self.client = create_alpaca_trading_client(
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
        payload = order_request_to_alpaca_payload(order_request)
        response = self._call("submit_order", self.client.submit_order, payload)
        order = alpaca_order_to_domain(response)
        metadata = dict(order.metadata)
        metadata.update(
            {
                "strategy_id": order_request.strategy_id,
                "requested_notional": order_request.notional,
                "time_in_force": order_request.time_in_force.value,
            }
        )
        order = replace(order, metadata=metadata)
        self._cache_order(order)
        self._filled_quantities_by_order_id.setdefault(order.order_id, 0.0)
        return order

    def cancel_order(self, order_id: str) -> Order:
        self._require_connected()
        response = self._call("cancel_order", self.client.cancel_order, order_id)
        if response:
            order = alpaca_order_to_domain(response)
        else:
            order = self.get_order(order_id)
            if order is None:
                cached = self._orders.get(order_id)
                if cached is None:
                    raise BrokerError(f"unknown Alpaca order after cancel: {order_id}")
                order = replace(cached, status=OrderStatus.CANCELED)
        return self._cache_order(order)

    def get_order(self, order_id: str) -> Order | None:
        self._require_connected()
        try:
            response = self.client.get_order(order_id)
        except AlpacaAPIError as exc:
            if exc.status_code == 404:
                return None
            raise BrokerError(f"alpaca get_order failed: {exc}") from exc
        except Exception as exc:
            raise BrokerError(f"alpaca get_order failed: {exc}") from exc
        order = alpaca_order_to_domain(response)
        return self._cache_order(order)

    def list_orders(
        self,
        status: OrderStatus | str | None = None,
        symbol: str | None = None,
    ) -> list[Order]:
        self._require_connected()
        query_status = alpaca_query_status(status)
        response = self._call(
            "list_orders",
            self.client.list_orders,
            status=query_status,
            symbols=normalize_symbol(symbol) if symbol else None,
            direction="asc",
        )
        orders = [alpaca_order_to_domain(item) for item in response]
        domain_status = should_filter_domain_status(status)
        if domain_status is not None:
            orders = [order for order in orders if order.status == domain_status]
        return [self._cache_order(order) for order in orders]

    def get_account(self) -> Account:
        self._require_connected()
        response = self._call("get_account", self.client.get_account)
        return alpaca_account_to_domain(response)

    def get_positions(self) -> list[Position]:
        self._require_connected()
        response = self._call("list_positions", self.client.list_positions)
        return [alpaca_position_to_domain(item) for item in response]

    def poll_fills(self, since: datetime | None = None) -> list[Fill]:
        self._require_connected()
        after = None
        if since is not None:
            after = normalize_timestamp(since).isoformat().replace("+00:00", "Z")
        response = self._call(
            "list_orders",
            self.client.list_orders,
            status="all",
            after=after,
            limit=500,
            direction="asc",
        )
        fills: list[Fill] = []
        source = "alpaca_paper" if self.broker_config.paper is not False else "alpaca_live"
        for payload in response:
            order = alpaca_order_to_domain(payload)
            previous_quantity = self._filled_quantities_by_order_id.get(order.order_id, 0.0)
            fill = alpaca_order_to_fill_delta(
                payload,
                previous_quantity,
                source=source,
            )
            self._cache_order(order)
            self._filled_quantities_by_order_id[order.order_id] = order.filled_quantity
            if fill is not None:
                fills.append(fill)
        return fills

    def is_market_open(self, timestamp: datetime) -> bool:
        self._require_connected()
        response = self._call("get_clock", self.client.get_clock)
        if "is_open" in response:
            return bool(response["is_open"])
        return normalize_timestamp(timestamp).weekday() < 5

    def _ensure_paper_only(self) -> None:
        broker_type = self.broker_config.broker_type.lower()
        if self.broker_config.paper is False or broker_type == "alpaca_live":
            raise LiveSafetyError("Phase 6 only enables Alpaca paper brokerage")

    def _require_connected(self) -> None:
        if not self._connected or self.client is None:
            raise BrokerError("AlpacaBrokerage is not connected")

    def _call(self, name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AlpacaAPIError as exc:
            raise BrokerError(f"alpaca {name} failed: {exc}") from exc
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"alpaca {name} failed: {exc}") from exc

    def _cache_order(self, order: Order) -> Order:
        cached = self._orders.get(order.order_id)
        if cached is not None:
            metadata = dict(cached.metadata)
            metadata.update(order.metadata)
            order = replace(order, metadata=metadata)
        self._orders[order.order_id] = order
        return order


def _mock_mode(broker_config: BrokerConfig) -> bool:
    safety = dict(broker_config.safety)
    return bool(safety.get("mock_mode") or safety.get("dry_run"))


__all__ = ["AlpacaBrokerage"]
