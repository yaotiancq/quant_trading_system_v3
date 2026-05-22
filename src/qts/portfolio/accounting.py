"""Internal portfolio accounting from normalized fills."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from qts.core import PortfolioError
from qts.domain import (
    Account,
    CashLedgerEntry,
    Fill,
    Order,
    OrderSide,
    PortfolioSnapshot,
    Position,
    TradeLedgerEntry,
    normalize_currency,
    normalize_symbol,
    normalize_timestamp,
)


class DefaultPortfolio:
    """Long-only portfolio accounting used by Phase 5 backtests."""

    def __init__(
        self,
        starting_cash: float = 100000.0,
        *,
        currency: str = "USD",
        account_id: str = "portfolio",
        timestamp: datetime | None = None,
    ) -> None:
        self.account_id = account_id
        self.currency = normalize_currency(currency)
        self._starting_cash = float(starting_cash)
        self._cash = float(starting_cash)
        self._realized_pnl = 0.0
        self._positions: dict[str, Position] = {}
        self._trade_ledger: list[TradeLedgerEntry] = []
        self._cash_ledger: list[CashLedgerEntry] = []
        self._processed_fill_ids: set[str] = set()
        self._last_prices: dict[str, float] = {}
        self._last_snapshot = self._build_snapshot(
            normalize_timestamp(timestamp or datetime.now(timezone.utc))
        )

    def initialize(
        self,
        starting_cash: float,
        base_currency: str = "USD",
        *,
        timestamp: datetime | None = None,
    ) -> None:
        self.currency = normalize_currency(base_currency)
        self._starting_cash = float(starting_cash)
        self._cash = float(starting_cash)
        self._realized_pnl = 0.0
        self._positions.clear()
        self._trade_ledger.clear()
        self._cash_ledger.clear()
        self._processed_fill_ids.clear()
        self._last_prices.clear()
        self._last_snapshot = self._build_snapshot(
            normalize_timestamp(timestamp or datetime.now(timezone.utc))
        )

    def apply_fill(self, fill: Fill, order: Order | None = None) -> PortfolioSnapshot:
        if fill.fill_id in self._processed_fill_ids:
            return self._last_snapshot
        self._processed_fill_ids.add(fill.fill_id)

        symbol = normalize_symbol(fill.symbol)
        notional = fill.quantity * fill.price
        realized_delta = 0.0
        position = self._positions.get(symbol)

        if fill.side == OrderSide.BUY:
            previous_quantity = position.quantity if position else 0.0
            previous_cost = position.average_cost if position else 0.0
            new_quantity = previous_quantity + fill.quantity
            if new_quantity <= 0:
                raise PortfolioError("buy fill produced non-positive position quantity")
            average_cost = (
                previous_quantity * previous_cost + fill.quantity * fill.price
            ) / new_quantity
            self._cash -= notional + fill.commission
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=new_quantity,
                average_cost=average_cost,
                market_price=fill.price,
                updated_at=fill.timestamp,
            )
        else:
            if position is None or position.quantity + 1e-9 < fill.quantity:
                raise PortfolioError(f"sell fill exceeds current position for {symbol}")
            realized_delta = (fill.price - position.average_cost) * fill.quantity - fill.commission
            self._realized_pnl += realized_delta
            self._cash += notional - fill.commission
            new_quantity = position.quantity - fill.quantity
            if new_quantity <= 1e-9:
                self._positions.pop(symbol, None)
            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_quantity,
                    average_cost=position.average_cost,
                    market_price=fill.price,
                    updated_at=fill.timestamp,
                )

        self._last_prices[symbol] = fill.price
        self._record_trade(fill, order, realized_delta)
        self._record_cash_entries(fill, notional)
        return self.mark_to_market({symbol: fill.price}, fill.timestamp)

    def mark_to_market(
        self,
        latest_prices_by_symbol: dict[str, float],
        timestamp: datetime,
    ) -> PortfolioSnapshot:
        normalized_timestamp = normalize_timestamp(timestamp)
        for raw_symbol, price in latest_prices_by_symbol.items():
            symbol = normalize_symbol(raw_symbol)
            self._last_prices[symbol] = float(price)
            position = self._positions.get(symbol)
            if position is None:
                continue
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=position.quantity,
                average_cost=position.average_cost,
                market_price=float(price),
                updated_at=normalized_timestamp,
            )
        self._last_snapshot = self._build_snapshot(normalized_timestamp)
        return self._last_snapshot

    def get_position(self, symbol: str) -> Position | None:
        position = self._positions.get(normalize_symbol(symbol))
        return replace(position) if position is not None else None

    def get_account_snapshot(self) -> PortfolioSnapshot:
        return self._last_snapshot

    def get_account(self) -> Account:
        snapshot = self._last_snapshot
        return Account(
            account_id=self.account_id,
            timestamp=snapshot.timestamp,
            currency=self.currency,
            cash=snapshot.cash,
            equity=snapshot.equity,
            buying_power=max(snapshot.cash, 0.0),
            gross_exposure=snapshot.gross_exposure,
            net_exposure=snapshot.net_exposure,
            realized_pnl=snapshot.realized_pnl,
            unrealized_pnl=snapshot.unrealized_pnl,
        )

    def get_trade_ledger(self) -> list[TradeLedgerEntry]:
        return list(self._trade_ledger)

    def get_cash_ledger(self) -> list[CashLedgerEntry]:
        return list(self._cash_ledger)

    def reconcile(self, broker_account: Account, broker_positions: list[Position]) -> dict[str, object]:
        raise PortfolioError("broker reconciliation is out of scope for Phase 5 backtests")

    def _record_trade(self, fill: Fill, order: Order | None, realized_delta: float) -> None:
        position = self._positions.get(fill.symbol)
        strategy_id = order.metadata.get("strategy_id") if order is not None else None
        self._trade_ledger.append(
            TradeLedgerEntry(
                entry_id=f"trade-{fill.fill_id}",
                fill_id=fill.fill_id,
                order_id=fill.order_id,
                strategy_id=strategy_id,
                symbol=fill.symbol,
                timestamp=fill.timestamp,
                side=fill.side,
                quantity=fill.quantity,
                price=fill.price,
                commission=fill.commission,
                realized_pnl_delta=realized_delta,
                position_quantity_after=position.quantity if position is not None else 0.0,
                average_cost_after=position.average_cost if position is not None else 0.0,
            )
        )

    def _record_cash_entries(self, fill: Fill, notional: float) -> None:
        trade_amount = notional if fill.side == OrderSide.SELL else -notional
        cash_after_trade = self._cash + fill.commission if fill.commission else self._cash
        self._cash_ledger.append(
            CashLedgerEntry(
                entry_id=f"cash-{fill.fill_id}-trade",
                timestamp=fill.timestamp,
                event_type="trade",
                amount=trade_amount,
                currency=self.currency,
                cash_after=cash_after_trade,
                related_fill_id=fill.fill_id,
                related_order_id=fill.order_id,
                description=f"{fill.side.value} {fill.quantity:g} {fill.symbol} @ {fill.price:g}",
            )
        )
        if fill.commission:
            self._cash_ledger.append(
                CashLedgerEntry(
                    entry_id=f"cash-{fill.fill_id}-commission",
                    timestamp=fill.timestamp,
                    event_type="commission",
                    amount=-fill.commission,
                    currency=self.currency,
                    cash_after=self._cash,
                    related_fill_id=fill.fill_id,
                    related_order_id=fill.order_id,
                    description="broker commission",
                )
            )

    def _build_snapshot(self, timestamp: datetime) -> PortfolioSnapshot:
        positions = [self._positions[symbol] for symbol in sorted(self._positions)]
        positions_value = sum(abs(position.market_value or 0.0) for position in positions)
        net_exposure = sum(position.quantity * (position.market_price or position.average_cost) for position in positions)
        unrealized_pnl = sum(position.unrealized_pnl or 0.0 for position in positions)
        equity = self._cash + sum(position.quantity * (position.market_price or position.average_cost) for position in positions)
        return PortfolioSnapshot(
            timestamp=timestamp,
            cash=self._cash,
            equity=equity,
            positions_value=positions_value,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized_pnl,
            gross_exposure=positions_value,
            net_exposure=net_exposure,
            positions=positions,
            metadata={
                "account_id": self.account_id,
                "currency": self.currency,
                "starting_cash": self._starting_cash,
                "buying_power": max(self._cash, 0.0),
            },
        )


__all__ = ["DefaultPortfolio"]
