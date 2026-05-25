"""Broker/internal reconciliation health checks."""

from __future__ import annotations

from typing import Any, Protocol

from qts.brokers.interfaces import Brokerage
from qts.domain import Account, Position

from .types import HealthCheckResult, HealthStatus


class ReconciliablePortfolio(Protocol):
    """Portfolio methods needed for broker reconciliation."""

    def reconcile(self, broker_account: Account, broker_positions: list[Position]) -> dict[str, object]:
        """Compare internal and broker state."""


class BrokerReconciliationCheck:
    """Run broker/internal reconciliation and expose it as a health check."""

    def __init__(
        self,
        portfolio: ReconciliablePortfolio,
        brokerage: Brokerage,
        *,
        name: str = "broker_reconciliation",
    ) -> None:
        self.portfolio = portfolio
        self.brokerage = brokerage
        self._name = name
        self.last_result: dict[str, object] | None = None

    @property
    def name(self) -> str:
        return self._name

    def run(self) -> HealthCheckResult:
        result = self.portfolio.reconcile(
            self.brokerage.get_account(),
            self.brokerage.get_positions(),
        )
        self.last_result = result
        matched = bool(result.get("matched"))
        return HealthCheckResult(
            self.name,
            HealthStatus.OK if matched else HealthStatus.CRITICAL,
            "broker reconciliation matched" if matched else "broker reconciliation mismatch",
            details=_serializable_details(result),
        )


def _serializable_details(result: dict[str, object]) -> dict[str, Any]:
    return dict(result)


__all__ = ["BrokerReconciliationCheck", "ReconciliablePortfolio"]
