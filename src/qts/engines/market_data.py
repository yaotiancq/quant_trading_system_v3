"""Runtime market-data configuration helpers for engines."""

from __future__ import annotations

from qts.core import ConfigurationError
from qts.domain import RuntimeConfig


EVENT_DRIVEN_MARKET_DATA_PROVIDERS = {
    "external",
    "external_events",
    "externally_supplied",
    "fake_stream",
    "manual",
}


def resolve_event_market_data_provider(config: RuntimeConfig, *, engine_name: str) -> str:
    """Validate that the configured provider can supply runtime market events."""
    provider = str(config.market_data.get("provider", "")).strip().lower()
    if provider not in EVENT_DRIVEN_MARKET_DATA_PROVIDERS:
        supported = ", ".join(sorted(EVENT_DRIVEN_MARKET_DATA_PROVIDERS))
        raise ConfigurationError(
            f"{engine_name} currently supports event-driven market data only; "
            f"set market_data.provider to one of: {supported}"
        )
    return provider


__all__ = ["EVENT_DRIVEN_MARKET_DATA_PROVIDERS", "resolve_event_market_data_provider"]
