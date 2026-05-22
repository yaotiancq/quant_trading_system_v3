from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qts.monitoring import (
    AlertManager,
    AlertSeverity,
    CallableHealthCheck,
    HealthCheckResult,
    HealthMonitor,
    HealthStatus,
    InMemoryAlertSink,
    RecoveryManager,
    RuntimeMetricsLogger,
)


class HealthAlertRecoveryTests(unittest.TestCase):
    def test_health_monitor_summarizes_failed_checks(self) -> None:
        monitor = HealthMonitor(
            [
                CallableHealthCheck(
                    "ok",
                    lambda: HealthCheckResult("ok", HealthStatus.OK, "fine"),
                ),
                CallableHealthCheck("boom", lambda: (_ for _ in ()).throw(RuntimeError("bad"))),
            ]
        )

        summary = monitor.summary()

        self.assertEqual(summary["status"], "CRITICAL")
        self.assertFalse(summary["healthy"])
        self.assertEqual(len(summary["checks"]), 2)

    def test_alert_manager_records_alerts(self) -> None:
        sink = InMemoryAlertSink()
        manager = AlertManager([sink])

        alert = manager.emit(AlertSeverity.CRITICAL, "test", "failure", details={"x": 1})

        self.assertEqual(sink.alerts, [alert])
        self.assertEqual(alert.to_dict()["severity"], "CRITICAL")

    def test_metrics_logger_records_and_writes_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.jsonl"
            logger = RuntimeMetricsLogger(path)
            logger.increment("events_total", tags={"mode": "live"})
            logger.increment("events_total", tags={"mode": "live"})

            self.assertEqual(logger.latest("events_total").value, 2.0)  # type: ignore[union-attr]
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_recovery_manager_alerts_and_stops_engine(self) -> None:
        class Engine:
            def __init__(self) -> None:
                self.reason: str | None = None

            def stop(self, reason: str | None = None) -> None:
                self.reason = reason

        sink = InMemoryAlertSink()
        alerts = AlertManager([sink])
        metrics = RuntimeMetricsLogger()
        recovery = RecoveryManager(alert_manager=alerts, metrics_logger=metrics)
        engine = Engine()

        result = recovery.handle_failure(RuntimeError("unsafe"), source="live", engine=engine)

        self.assertTrue(result.success)
        self.assertEqual(result.action, "stop_engine")
        self.assertIn("RuntimeError", engine.reason or "")
        self.assertEqual(sink.alerts[0].severity, AlertSeverity.CRITICAL)
        self.assertEqual(metrics.latest("runtime_failures_total").value, 1.0)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
