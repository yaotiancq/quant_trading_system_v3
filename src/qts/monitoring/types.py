"""Shared monitoring and operational-readiness types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from qts.domain import normalize_timestamp


class HealthStatus(Enum):
    """Health status ordered from healthy to unsafe."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertSeverity(Enum):
    """Alert severity values used by alert sinks."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class HealthCheckResult:
    """Result from one health check."""

    name: str
    status: HealthStatus | str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name).strip())
        if not self.name:
            raise ValueError("health check name must be non-empty")
        object.__setattr__(self, "status", coerce_health_status(self.status))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "details", dict(self.details))

    @property
    def healthy(self) -> bool:
        return self.status == HealthStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "healthy": self.healthy,
            "message": self.message,
            "timestamp": _timestamp_text(self.timestamp),
            "details": _serialize(self.details),
        }


@dataclass(frozen=True)
class RuntimeMetric:
    """One runtime metric sample."""

    name: str
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name).strip())
        if not self.name:
            raise ValueError("metric name must be non-empty")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "tags", {str(key): str(value) for key, value in self.tags.items()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": _timestamp_text(self.timestamp),
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class AlertEvent:
    """Operational alert event."""

    severity: AlertSeverity | str
    source: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", coerce_alert_severity(self.severity))
        object.__setattr__(self, "source", str(self.source).strip())
        if not self.source:
            raise ValueError("alert source must be non-empty")
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "details", dict(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "source": self.source,
            "message": self.message,
            "timestamp": _timestamp_text(self.timestamp),
            "details": _serialize(self.details),
        }


@dataclass(frozen=True)
class RecoveryResult:
    """Outcome from a recovery action."""

    action: str
    success: bool
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", str(self.action).strip())
        if not self.action:
            raise ValueError("recovery action must be non-empty")
        object.__setattr__(self, "success", bool(self.success))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        object.__setattr__(self, "details", dict(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "success": self.success,
            "message": self.message,
            "timestamp": _timestamp_text(self.timestamp),
            "details": _serialize(self.details),
        }


def coerce_health_status(value: HealthStatus | str) -> HealthStatus:
    if isinstance(value, HealthStatus):
        return value
    return HealthStatus(str(value).strip().upper())


def coerce_alert_severity(value: AlertSeverity | str) -> AlertSeverity:
    if isinstance(value, AlertSeverity):
        return value
    return AlertSeverity(str(value).strip().upper())


def _timestamp_text(value: datetime) -> str:
    return normalize_timestamp(value).isoformat().replace("+00:00", "Z")


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return _timestamp_text(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


__all__ = [
    "AlertEvent",
    "AlertSeverity",
    "HealthCheckResult",
    "HealthStatus",
    "RecoveryResult",
    "RuntimeMetric",
    "coerce_alert_severity",
    "coerce_health_status",
]
