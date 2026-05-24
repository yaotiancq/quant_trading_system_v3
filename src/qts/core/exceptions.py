"""Project-wide exception hierarchy."""

from __future__ import annotations


class QTSError(Exception):
    """Base class for controlled project errors."""


class ConfigurationError(QTSError):
    """Raised when configuration is missing, invalid, or unsafe."""


class ClockError(QTSError):
    """Raised when a clock receives an invalid operation."""


class DataError(QTSError):
    """Raised for market data validation or provider failures."""


class CalendarError(QTSError):
    """Raised when a market calendar/session cannot be resolved."""


class FeatureError(QTSError):
    """Raised for feature schema or indicator failures."""


class StrategyError(QTSError):
    """Raised for strategy initialization or runtime failures."""


class RiskError(QTSError):
    """Raised for risk configuration or evaluation failures."""


class ExecutionError(QTSError):
    """Raised for execution workflow failures."""


class BrokerError(QTSError):
    """Raised for normalized brokerage failures."""


class PortfolioError(QTSError):
    """Raised for portfolio accounting failures."""


class ReconciliationError(QTSError):
    """Raised when broker and internal state cannot be reconciled."""


class LiveSafetyError(QTSError):
    """Raised when live-trading safety gates are not satisfied."""


__all__ = [
    "BrokerError",
    "CalendarError",
    "ClockError",
    "ConfigurationError",
    "DataError",
    "ExecutionError",
    "FeatureError",
    "LiveSafetyError",
    "PortfolioError",
    "QTSError",
    "ReconciliationError",
    "RiskError",
    "StrategyError",
]
