"""Stable enum values used across the trading system."""

from __future__ import annotations

from enum import StrEnum


class RuntimeMode(StrEnum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    OPTION = "OPTION"
    FUTURE = "FUTURE"


class BarTimeframe(StrEnum):
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"


class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"
    HOLD = "HOLD"
    EXIT = "EXIT"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(StrEnum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


OPEN_ORDER_STATUSES = frozenset(
    {
        OrderStatus.NEW,
        OrderStatus.ACCEPTED,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
    }
)


class TimeInForce(StrEnum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class RiskDecisionStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class DataAdjustment(StrEnum):
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    DIVIDEND_ADJUSTED = "DIVIDEND_ADJUSTED"
    TOTAL_RETURN = "TOTAL_RETURN"


class BrokerEventType(StrEnum):
    ORDER_UPDATE = "ORDER_UPDATE"
    FILL = "FILL"
    ACCOUNT_UPDATE = "ACCOUNT_UPDATE"
    POSITION_UPDATE = "POSITION_UPDATE"


__all__ = [
    "AssetClass",
    "BarTimeframe",
    "BrokerEventType",
    "DataAdjustment",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "OPEN_ORDER_STATUSES",
    "RiskDecisionStatus",
    "RuntimeMode",
    "SignalDirection",
    "TimeInForce",
]
