"""Recovery behavior for live/paper runtime failures."""

from __future__ import annotations

from typing import Any

from .alerts import AlertManager
from .metrics import RuntimeMetricsLogger
from .types import AlertSeverity, RecoveryResult


class RecoveryManager:
    """Apply conservative recovery actions after critical failures."""

    def __init__(
        self,
        *,
        alert_manager: AlertManager | None = None,
        metrics_logger: RuntimeMetricsLogger | None = None,
    ) -> None:
        self.alert_manager = alert_manager
        self.metrics_logger = metrics_logger
        self.results: list[RecoveryResult] = []

    def handle_failure(
        self,
        error: BaseException,
        *,
        source: str,
        engine: Any | None = None,
        stop_engine: bool = True,
    ) -> RecoveryResult:
        if self.metrics_logger is not None:
            self.metrics_logger.increment(
                "runtime_failures_total",
                tags={"source": source, "error_type": type(error).__name__},
            )
        if self.alert_manager is not None:
            self.alert_manager.emit(
                AlertSeverity.CRITICAL,
                source,
                str(error),
                details={"error_type": type(error).__name__},
            )

        if stop_engine and engine is not None and hasattr(engine, "stop"):
            try:
                engine.stop(reason=f"recovery after {type(error).__name__}")
            except TypeError:
                engine.stop()
            result = RecoveryResult(
                action="stop_engine",
                success=True,
                message="engine stop requested after failure",
                details={"source": source, "error_type": type(error).__name__},
            )
        else:
            result = RecoveryResult(
                action="alert_only",
                success=True,
                message="failure recorded without engine stop",
                details={"source": source, "error_type": type(error).__name__},
            )
        self.results.append(result)
        return result


__all__ = ["RecoveryManager"]
