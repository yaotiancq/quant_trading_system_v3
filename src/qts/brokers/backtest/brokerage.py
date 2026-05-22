"""Simulated backtest brokerage implementation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from qts.core import BrokerError
from qts.domain import (
    Account,
    Bar,
    BrokerConfig,
    Fill,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Quote,
    TimeInForce,
    Trade,
    normalize_symbol,
    normalize_timestamp,
)
from qts.execution import OPEN_ORDER_STATUSES


VALID_FILL_POLICIES = {
    "next_bar_open",
    "next_bar_close",
    "next_bar_typical_price",
    "quote_bid_ask",
}


class BacktestBrokerage:
    """Stateful simulated broker for bar/quote/trade driven backtests."""

    def __init__(
        self,
        broker_config: BrokerConfig | None = None,
        *,
        starting_cash: float = 100000.0,
        currency: str = "USD",
        account_id: str = "backtest",
        fill_policy: str | None = None,
        commission_model: dict[str, Any] | None = None,
        slippage_model: dict[str, Any] | None = None,
        max_fill_quantity_per_event: float | None = None,
    ) -> None:
        self.broker_config = broker_config or BrokerConfig(broker_type="backtest")
        self.account_id = account_id
        self.currency = currency
        self.fill_policy = fill_policy or self.broker_config.fill_policy or "next_bar_open"
        self.commission_model = dict(commission_model or self.broker_config.commission_model)
        self.slippage_model = dict(slippage_model or self.broker_config.slippage_model)
        self.max_fill_quantity_per_event = max_fill_quantity_per_event
        self._connected = False
        self._order_counter = 0
        self._fill_counter = 0
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._positions: dict[str, Position] = {}
        self._latest_prices: dict[str, float] = {}
        self._last_timestamp = datetime.now(timezone.utc)
        self._starting_cash = float(starting_cash)
        self._cash = float(starting_cash)
        self._validate_fill_policy()

    def connect(self, broker_config: BrokerConfig | None = None) -> None:
        if broker_config is not None:
            self.broker_config = broker_config
            self.fill_policy = broker_config.fill_policy or self.fill_policy
            self.commission_model = dict(broker_config.commission_model)
            self.slippage_model = dict(broker_config.slippage_model)
            self._validate_fill_policy()
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def reset(
        self,
        starting_account: Account | None = None,
        *,
        starting_cash: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        if starting_account is not None:
            self.account_id = starting_account.account_id or self.account_id
            self.currency = starting_account.currency
            self._starting_cash = float(starting_account.cash)
            self._cash = float(starting_account.cash)
            self._last_timestamp = starting_account.timestamp
        else:
            cash = self._starting_cash if starting_cash is None else float(starting_cash)
            self._starting_cash = cash
            self._cash = cash
            self._last_timestamp = normalize_timestamp(timestamp or datetime.now(timezone.utc))
        self._orders.clear()
        self._fills.clear()
        self._positions.clear()
        self._latest_prices.clear()
        self._order_counter = 0
        self._fill_counter = 0

    def set_fill_model(self, fill_model: dict[str, Any] | str) -> None:
        if isinstance(fill_model, str):
            self.fill_policy = fill_model
        else:
            if "fill_policy" in fill_model:
                self.fill_policy = str(fill_model["fill_policy"])
            if "max_fill_quantity_per_event" in fill_model:
                self.max_fill_quantity_per_event = float(fill_model["max_fill_quantity_per_event"])
        self._validate_fill_policy()

    def set_commission_model(self, commission_model: dict[str, Any]) -> None:
        self.commission_model = dict(commission_model)

    def set_slippage_model(self, slippage_model: dict[str, Any]) -> None:
        self.slippage_model = dict(slippage_model)

    def submit_order(self, order_request: OrderRequest) -> Order:
        self._require_connected()
        self._order_counter += 1
        order_id = f"bt-order-{self._order_counter:06d}"
        metadata = dict(order_request.metadata)
        metadata.update(
            {
                "strategy_id": order_request.strategy_id,
                "time_in_force": order_request.time_in_force.value,
                "requested_notional": order_request.notional,
            }
        )

        rejection_reason = self._submission_rejection_reason(order_request)
        status = OrderStatus.REJECTED if rejection_reason else OrderStatus.ACCEPTED
        order = Order(
            order_id=order_id,
            client_order_id=order_request.client_order_id,
            symbol=order_request.symbol,
            created_at=order_request.timestamp,
            updated_at=order_request.timestamp,
            side=order_request.side,
            quantity=order_request.quantity,
            filled_quantity=0.0,
            remaining_quantity=order_request.quantity,
            order_type=order_request.order_type,
            status=status,
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            rejection_reason=rejection_reason,
            metadata=metadata,
        )
        self._orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self._require_order(order_id)
        if order.status not in OPEN_ORDER_STATUSES:
            return order
        updated = replace(
            order,
            status=OrderStatus.CANCELED,
            updated_at=self._last_timestamp,
        )
        self._orders[order_id] = updated
        return updated

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def list_orders(
        self,
        status: OrderStatus | str | None = None,
        symbol: str | None = None,
    ) -> list[Order]:
        normalized_status = OrderStatus(status) if isinstance(status, str) else status
        normalized_symbol = normalize_symbol(symbol) if symbol else None
        orders = [
            order
            for order in self._orders.values()
            if (normalized_status is None or order.status == normalized_status)
            and (normalized_symbol is None or order.symbol == normalized_symbol)
        ]
        return sorted(orders, key=lambda order: (order.created_at, order.order_id))

    def get_account(self) -> Account:
        positions_value = self._positions_value()
        return Account(
            account_id=self.account_id,
            timestamp=self._last_timestamp,
            currency=self.currency,
            cash=self._cash,
            equity=self._cash + positions_value,
            buying_power=max(self._cash, 0.0),
            gross_exposure=sum(
                abs(position.quantity * self._position_price(position))
                for position in self._positions.values()
            ),
            net_exposure=sum(
                position.quantity * self._position_price(position)
                for position in self._positions.values()
            ),
        )

    def get_positions(self) -> list[Position]:
        return [self._positions[symbol] for symbol in sorted(self._positions)]

    def poll_fills(self, since: datetime | None = None) -> list[Fill]:
        if since is None:
            return list(self._fills)
        normalized_since = normalize_timestamp(since)
        return [fill for fill in self._fills if fill.timestamp > normalized_since]

    def is_market_open(self, timestamp: datetime) -> bool:
        normalized = normalize_timestamp(timestamp)
        return normalized.weekday() < 5

    def on_market_event(self, market_event: Bar | Quote | Trade) -> list[Fill]:
        self._require_connected()
        timestamp = normalize_timestamp(market_event.timestamp)
        self._last_timestamp = timestamp
        symbol = normalize_symbol(market_event.symbol)
        mark_price = self._mark_price(market_event)
        if mark_price is not None:
            self._latest_prices[symbol] = mark_price
            self._mark_position(symbol, mark_price, timestamp)

        fills: list[Fill] = []
        for order in list(self.list_orders(symbol=symbol)):
            if order.status not in OPEN_ORDER_STATUSES:
                continue
            if self._expire_if_needed(order, timestamp):
                continue
            if timestamp <= order.created_at:
                continue
            submitted = self._mark_submitted(order, timestamp)
            fill_price = self._fill_price(submitted, market_event)
            if fill_price is None:
                continue
            fill = self._create_fill(submitted, fill_price, timestamp)
            if fill is None:
                continue
            self._fills.append(fill)
            self._apply_fill_to_state(fill)
            self._update_order_after_fill(submitted.order_id, fill)
            fills.append(fill)
        return fills

    def _create_fill(self, order: Order, base_price: float, timestamp: datetime) -> Fill | None:
        quantity = self._fill_quantity(order, base_price)
        if quantity <= 0:
            return None
        fill_price, slippage = self._apply_slippage(base_price, order.side)
        commission = self._commission(quantity, fill_price)
        notional = quantity * fill_price

        if order.side == OrderSide.BUY and notional + commission > self._cash + 1e-9:
            self._reject_open_order(order, "insufficient_buying_power", timestamp)
            return None
        if order.side == OrderSide.SELL:
            position = self._positions.get(order.symbol)
            if position is None or position.quantity + 1e-9 < quantity:
                self._reject_open_order(order, "insufficient_position", timestamp)
                return None

        self._fill_counter += 1
        return Fill(
            fill_id=f"bt-fill-{self._fill_counter:06d}",
            order_id=order.order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            timestamp=timestamp,
            side=order.side,
            quantity=quantity,
            price=fill_price,
            commission=commission,
            slippage=slippage,
            liquidity_flag="simulated",
            source="backtest",
        )

    def _apply_fill_to_state(self, fill: Fill) -> None:
        notional = fill.quantity * fill.price
        position = self._positions.get(fill.symbol)
        if fill.side == OrderSide.BUY:
            self._cash -= notional + fill.commission
            previous_quantity = position.quantity if position else 0.0
            previous_cost = position.average_cost if position else 0.0
            new_quantity = previous_quantity + fill.quantity
            average_cost = (
                (previous_quantity * previous_cost + fill.quantity * fill.price) / new_quantity
            )
            self._positions[fill.symbol] = Position(
                symbol=fill.symbol,
                quantity=new_quantity,
                average_cost=average_cost,
                market_price=fill.price,
                updated_at=fill.timestamp,
            )
            self._latest_prices[fill.symbol] = fill.price
            return

        self._cash += notional - fill.commission
        if position is None:
            return
        new_quantity = position.quantity - fill.quantity
        if new_quantity <= 1e-9:
            self._positions.pop(fill.symbol, None)
            self._latest_prices[fill.symbol] = fill.price
            return
        self._positions[fill.symbol] = Position(
            symbol=fill.symbol,
            quantity=new_quantity,
            average_cost=position.average_cost,
            market_price=fill.price,
            updated_at=fill.timestamp,
        )
        self._latest_prices[fill.symbol] = fill.price

    def _update_order_after_fill(self, order_id: str, fill: Fill) -> Order:
        order = self._require_order(order_id)
        previous_filled = order.filled_quantity
        filled_quantity = previous_filled + fill.quantity
        target_quantity = order.quantity
        if target_quantity is None:
            requested_notional = order.metadata.get("requested_notional")
            target_quantity = (
                float(requested_notional) / fill.price if requested_notional else filled_quantity
            )
        remaining_quantity = max(target_quantity - filled_quantity, 0.0)
        previous_notional = (order.average_fill_price or 0.0) * previous_filled
        average_fill_price = (previous_notional + fill.price * fill.quantity) / filled_quantity
        status = (
            OrderStatus.FILLED
            if remaining_quantity <= 1e-9
            else OrderStatus.PARTIALLY_FILLED
        )
        updated = replace(
            order,
            quantity=target_quantity,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_fill_price=average_fill_price,
            status=status,
            updated_at=fill.timestamp,
        )
        self._orders[order_id] = updated
        return updated

    def _fill_quantity(self, order: Order, fill_price: float) -> float:
        if order.quantity is not None:
            remaining = order.remaining_quantity
            target = remaining if remaining is not None else order.quantity - order.filled_quantity
        else:
            requested_notional = order.metadata.get("requested_notional")
            if not requested_notional:
                return 0.0
            target_quantity = float(requested_notional) / fill_price
            target = target_quantity - order.filled_quantity
        if self.max_fill_quantity_per_event is not None:
            target = min(target, self.max_fill_quantity_per_event)
        return max(target, 0.0)

    def _fill_price(self, order: Order, market_event: Bar | Quote | Trade) -> float | None:
        base_price = self._base_price(order, market_event)
        if base_price is None:
            return None
        order_type = order.order_type
        if order_type == OrderType.MARKET:
            return base_price
        if order_type == OrderType.LIMIT and self._limit_triggered(order, market_event, base_price):
            return _limit_fill_price(order, base_price)
        if order_type == OrderType.STOP and self._stop_triggered(order, market_event, base_price):
            return _stop_fill_price(order, base_price)
        if order_type == OrderType.STOP_LIMIT and self._stop_triggered(order, market_event, base_price):
            if self._limit_triggered(order, market_event, base_price):
                return _limit_fill_price(order, base_price)
        return None

    def _base_price(self, order: Order, market_event: Bar | Quote | Trade) -> float | None:
        if isinstance(market_event, Quote):
            if self.fill_policy != "quote_bid_ask":
                return None
            return market_event.ask_price if order.side == OrderSide.BUY else market_event.bid_price
        if isinstance(market_event, Trade):
            return market_event.price
        if self.fill_policy == "next_bar_open":
            return market_event.open
        if self.fill_policy == "next_bar_close":
            return market_event.close
        if self.fill_policy == "next_bar_typical_price":
            return (market_event.high + market_event.low + market_event.close) / 3.0
        return None

    def _limit_triggered(
        self,
        order: Order,
        market_event: Bar | Quote | Trade,
        base_price: float,
    ) -> bool:
        limit = order.limit_price
        if limit is None:
            return False
        if isinstance(market_event, Bar):
            return market_event.low <= limit if order.side == OrderSide.BUY else market_event.high >= limit
        return base_price <= limit if order.side == OrderSide.BUY else base_price >= limit

    def _stop_triggered(
        self,
        order: Order,
        market_event: Bar | Quote | Trade,
        base_price: float,
    ) -> bool:
        stop = order.stop_price
        if stop is None:
            return False
        if isinstance(market_event, Bar):
            return market_event.high >= stop if order.side == OrderSide.BUY else market_event.low <= stop
        return base_price >= stop if order.side == OrderSide.BUY else base_price <= stop

    def _apply_slippage(self, price: float, side: OrderSide) -> tuple[float, float]:
        model_type = str(self.slippage_model.get("type", "none")).lower()
        value = float(self.slippage_model.get("value", 0.0) or 0.0)
        if model_type in {"none", "zero"} or value == 0:
            return price, 0.0
        direction = 1.0 if side == OrderSide.BUY else -1.0
        if model_type == "bps":
            slippage = price * value / 10000.0
            return price + direction * slippage, abs(slippage)
        if model_type in {"fixed", "fixed_per_share"}:
            return price + direction * value, abs(value)
        raise BrokerError(f"unsupported slippage model: {model_type}")

    def _commission(self, quantity: float, price: float) -> float:
        model_type = str(self.commission_model.get("type", "none")).lower()
        value = float(self.commission_model.get("value", 0.0) or 0.0)
        if model_type in {"none", "zero"} or value == 0:
            return 0.0
        if model_type == "fixed":
            return value
        if model_type == "per_share":
            return quantity * value
        if model_type == "bps":
            return quantity * price * value / 10000.0
        raise BrokerError(f"unsupported commission model: {model_type}")

    def _submission_rejection_reason(self, order_request: OrderRequest) -> str | None:
        if order_request.side == OrderSide.BUY and order_request.notional is not None:
            estimated_commission = self._commission(1.0, float(order_request.notional))
            if order_request.notional + estimated_commission > self._cash + 1e-9:
                return "insufficient_buying_power"
        if (
            order_request.side == OrderSide.BUY
            and order_request.quantity is not None
            and order_request.limit_price is not None
        ):
            estimated_notional = order_request.quantity * order_request.limit_price
            estimated_commission = self._commission(order_request.quantity, order_request.limit_price)
            if estimated_notional + estimated_commission > self._cash + 1e-9:
                return "insufficient_buying_power"
        return None

    def _expire_if_needed(self, order: Order, timestamp: datetime) -> bool:
        tif = order.metadata.get("time_in_force")
        if tif != TimeInForce.DAY.value:
            return False
        if timestamp.date() <= order.created_at.date():
            return False
        updated = replace(
            order,
            status=OrderStatus.EXPIRED,
            updated_at=timestamp,
        )
        self._orders[order.order_id] = updated
        return True

    def _mark_submitted(self, order: Order, timestamp: datetime) -> Order:
        if order.status != OrderStatus.ACCEPTED:
            return order
        updated = replace(order, status=OrderStatus.SUBMITTED, updated_at=timestamp)
        self._orders[order.order_id] = updated
        return updated

    def _reject_open_order(self, order: Order, reason: str, timestamp: datetime) -> Order:
        updated = replace(
            order,
            status=OrderStatus.REJECTED,
            rejection_reason=reason,
            updated_at=timestamp,
        )
        self._orders[order.order_id] = updated
        return updated

    def _mark_price(self, market_event: Bar | Quote | Trade) -> float | None:
        if isinstance(market_event, Bar):
            return market_event.close
        if isinstance(market_event, Quote):
            return (market_event.bid_price + market_event.ask_price) / 2.0
        if isinstance(market_event, Trade):
            return market_event.price
        return None

    def _mark_position(self, symbol: str, price: float, timestamp: datetime) -> None:
        position = self._positions.get(symbol)
        if position is None:
            return
        self._positions[symbol] = Position(
            symbol=symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            market_price=price,
            updated_at=timestamp,
        )

    def _positions_value(self) -> float:
        return sum(
            position.quantity * self._position_price(position)
            for position in self._positions.values()
        )

    def _position_price(self, position: Position) -> float:
        return self._latest_prices.get(position.symbol) or position.market_price or position.average_cost

    def _require_connected(self) -> None:
        if not self._connected:
            raise BrokerError("backtest brokerage must be connected before use")

    def _require_order(self, order_id: str) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise BrokerError(f"unknown order: {order_id}")
        return order

    def _validate_fill_policy(self) -> None:
        if self.fill_policy not in VALID_FILL_POLICIES:
            allowed = ", ".join(sorted(VALID_FILL_POLICIES))
            raise BrokerError(f"unsupported fill policy {self.fill_policy!r}; expected one of {allowed}")


def _limit_fill_price(order: Order, base_price: float) -> float:
    if order.limit_price is None:
        return base_price
    return min(base_price, order.limit_price) if order.side == OrderSide.BUY else max(base_price, order.limit_price)


def _stop_fill_price(order: Order, base_price: float) -> float:
    if order.stop_price is None:
        return base_price
    return max(base_price, order.stop_price) if order.side == OrderSide.BUY else min(base_price, order.stop_price)


__all__ = ["BacktestBrokerage", "VALID_FILL_POLICIES"]
