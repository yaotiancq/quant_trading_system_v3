"""Clock implementations used by runtime modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from qts.domain import normalize_timestamp

from .exceptions import ClockError


class Clock(Protocol):
    """Common clock interface."""

    def now(self) -> datetime:
        """Return the current clock timestamp in UTC."""


@dataclass
class RealClock:
    """Clock backed by the system time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class ReplayClock:
    """Deterministic clock for historical replay and tests."""

    current_time: datetime
    step_size: timedelta | None = None

    def __post_init__(self) -> None:
        self.current_time = normalize_timestamp(self.current_time)
        if self.step_size is not None and self.step_size <= timedelta(0):
            raise ClockError("step_size must be positive")

    def now(self) -> datetime:
        return self.current_time

    def advance(
        self,
        timestamp: datetime | None = None,
        *,
        delta: timedelta | None = None,
    ) -> datetime:
        """Advance to an explicit timestamp, by a delta, or by the default step."""
        if timestamp is not None and delta is not None:
            raise ClockError("advance accepts either timestamp or delta, not both")

        if timestamp is not None:
            next_time = normalize_timestamp(timestamp)
        elif delta is not None:
            if delta <= timedelta(0):
                raise ClockError("delta must be positive")
            next_time = self.current_time + delta
        elif self.step_size is not None:
            next_time = self.current_time + self.step_size
        else:
            raise ClockError("advance requires timestamp, delta, or configured step_size")

        if next_time < self.current_time:
            raise ClockError("replay clock cannot move backward")

        self.current_time = next_time
        return self.current_time

    def reset(self, timestamp: datetime) -> datetime:
        self.current_time = normalize_timestamp(timestamp)
        return self.current_time


__all__ = ["Clock", "RealClock", "ReplayClock"]
