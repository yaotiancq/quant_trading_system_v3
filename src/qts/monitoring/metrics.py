"""Runtime metric logging helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import RuntimeMetric


class RuntimeMetricsLogger:
    """Collect runtime metrics and optionally mirror them to JSON lines."""

    def __init__(self, output_path: str | Path | None = None) -> None:
        self.output_path = Path(output_path) if output_path is not None else None
        self._metrics: list[RuntimeMetric] = []
        self._counters: dict[str, float] = {}

    def record(
        self,
        name: str,
        value: float,
        *,
        tags: dict[str, str] | None = None,
    ) -> RuntimeMetric:
        metric = RuntimeMetric(name=name, value=value, tags=dict(tags or {}))
        self._metrics.append(metric)
        self._write(metric.to_dict())
        return metric

    def increment(
        self,
        name: str,
        amount: float = 1.0,
        *,
        tags: dict[str, str] | None = None,
    ) -> RuntimeMetric:
        key = _counter_key(name, tags or {})
        self._counters[key] = self._counters.get(key, 0.0) + float(amount)
        return self.record(name, self._counters[key], tags=tags)

    def snapshot(self) -> list[dict[str, Any]]:
        return [metric.to_dict() for metric in self._metrics]

    def latest(self, name: str) -> RuntimeMetric | None:
        for metric in reversed(self._metrics):
            if metric.name == name:
                return metric
        return None

    def _write(self, payload: dict[str, Any]) -> None:
        if self.output_path is None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _counter_key(name: str, tags: dict[str, str]) -> str:
    tag_text = ",".join(f"{key}={value}" for key, value in sorted(tags.items()))
    return f"{name}|{tag_text}"


__all__ = ["RuntimeMetricsLogger"]
