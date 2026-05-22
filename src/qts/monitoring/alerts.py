"""Alert hooks for operational monitoring."""

from __future__ import annotations

import logging
from typing import Protocol

from .types import AlertEvent, AlertSeverity


class AlertSink(Protocol):
    """Receives alert events."""

    def send(self, alert: AlertEvent) -> None:
        """Send or store an alert."""


class InMemoryAlertSink:
    """Test and dry-run alert sink."""

    def __init__(self) -> None:
        self.alerts: list[AlertEvent] = []

    def send(self, alert: AlertEvent) -> None:
        self.alerts.append(alert)


class LoggingAlertSink:
    """Write alerts through the configured Python logger."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("qts.alerts")

    def send(self, alert: AlertEvent) -> None:
        level = logging.INFO
        if alert.severity == AlertSeverity.WARNING:
            level = logging.WARNING
        elif alert.severity == AlertSeverity.CRITICAL:
            level = logging.ERROR
        self.logger.log(level, "%s: %s", alert.source, alert.message, extra={"alert": alert.to_dict()})


class AlertManager:
    """Fan out alert events to one or more sinks."""

    def __init__(self, sinks: list[AlertSink] | None = None) -> None:
        self.sinks = list(sinks or [InMemoryAlertSink()])

    def emit(
        self,
        severity: AlertSeverity | str,
        source: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> AlertEvent:
        alert = AlertEvent(
            severity=severity,
            source=source,
            message=message,
            details=dict(details or {}),
        )
        for sink in self.sinks:
            sink.send(alert)
        return alert

    def critical_runtime_failure(
        self,
        source: str,
        error: BaseException,
        *,
        details: dict[str, object] | None = None,
    ) -> AlertEvent:
        payload = {"error_type": type(error).__name__, "error": str(error)}
        payload.update(dict(details or {}))
        return self.emit(AlertSeverity.CRITICAL, source, str(error), details=payload)


__all__ = ["AlertManager", "AlertSink", "InMemoryAlertSink", "LoggingAlertSink"]
