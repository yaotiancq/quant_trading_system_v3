"""Risk-layer result helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qts.domain import RiskDecisionStatus, TradeIntent


@dataclass
class RuleResult:
    rule_name: str
    status: RiskDecisionStatus
    reason: str
    intent: TradeIntent | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_name": self.rule_name,
            "status": self.status.value,
            "reason": self.reason,
            "details": dict(self.details),
        }
        if self.intent is not None:
            payload["intent"] = self.intent.to_dict()
        return payload


@dataclass
class SizingResult:
    intent: TradeIntent
    modified: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


__all__ = ["RuleResult", "SizingResult"]
