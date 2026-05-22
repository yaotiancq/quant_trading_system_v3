"""Health check orchestration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from qts.brokers import Brokerage
from qts.core import Clock, QTSError

from .types import HealthCheckResult, HealthStatus


class HealthCheck(Protocol):
    """A runnable health check."""

    @property
    def name(self) -> str:
        """Stable check name."""

    def run(self) -> HealthCheckResult:
        """Run the check and return a status."""


class CallableHealthCheck:
    """Wrap a callable as a health check."""

    def __init__(self, name: str, func: Callable[[], HealthCheckResult]) -> None:
        self._name = name
        self.func = func

    @property
    def name(self) -> str:
        return self._name

    def run(self) -> HealthCheckResult:
        return self.func()


class BrokerConnectionHealthCheck:
    """Checks that broker account access and market-clock access work."""

    def __init__(
        self,
        brokerage: Brokerage,
        *,
        clock: Clock | None = None,
        timestamp_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.brokerage = brokerage
        self.clock = clock
        self.timestamp_factory = timestamp_factory

    @property
    def name(self) -> str:
        return "broker_connection"

    def run(self) -> HealthCheckResult:
        try:
            account = self.brokerage.get_account()
            timestamp = self.clock.now() if self.clock is not None else None
            if timestamp is None and self.timestamp_factory is not None:
                timestamp = self.timestamp_factory()
            market_open = None
            if timestamp is not None:
                market_open = self.brokerage.is_market_open(timestamp)
        except Exception as exc:
            return HealthCheckResult(
                self.name,
                HealthStatus.CRITICAL,
                "broker connectivity check failed",
                details={"error_type": type(exc).__name__, "error": str(exc)},
            )
        return HealthCheckResult(
            self.name,
            HealthStatus.OK,
            "broker connectivity ok",
            details={
                "account_id": account.account_id,
                "currency": account.currency,
                "market_open": market_open,
            },
        )


class HealthMonitor:
    """Run and summarize health checks."""

    def __init__(self, checks: list[HealthCheck] | None = None) -> None:
        self.checks = list(checks or [])
        self.last_results: list[HealthCheckResult] = []

    def register(self, check: HealthCheck) -> None:
        self.checks.append(check)

    def run_all(self) -> list[HealthCheckResult]:
        results: list[HealthCheckResult] = []
        for check in self.checks:
            try:
                results.append(check.run())
            except QTSError as exc:
                results.append(_failed_result(check.name, exc))
            except Exception as exc:  # pragma: no cover - defensive monitor boundary
                results.append(_failed_result(check.name, exc))
        self.last_results = results
        return results

    def summary(self) -> dict[str, object]:
        results = self.run_all()
        status = overall_status(results)
        return {
            "status": status.value,
            "healthy": status == HealthStatus.OK,
            "checks": [result.to_dict() for result in results],
        }


def overall_status(results: list[HealthCheckResult]) -> HealthStatus:
    if any(result.status == HealthStatus.CRITICAL for result in results):
        return HealthStatus.CRITICAL
    if any(result.status == HealthStatus.WARNING for result in results):
        return HealthStatus.WARNING
    return HealthStatus.OK


def _failed_result(name: str, exc: BaseException) -> HealthCheckResult:
    return HealthCheckResult(
        name,
        HealthStatus.CRITICAL,
        "health check raised an exception",
        details={"error_type": type(exc).__name__, "error": str(exc)},
    )


__all__ = [
    "BrokerConnectionHealthCheck",
    "CallableHealthCheck",
    "HealthCheck",
    "HealthMonitor",
    "overall_status",
]
