"""Guarded live-trading engine scaffold."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from qts.brokers import Brokerage
from qts.core import ConfigurationError, LiveSafetyError, RealClock, ReconciliationError
from qts.domain import (
    Account,
    Bar,
    BrokerConfig,
    Fill,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    Quote,
    RuntimeConfig,
    RuntimeMode,
)
from qts.monitoring import (
    AlertManager,
    AlertSeverity,
    BrokerConnectionHealthCheck,
    BrokerReconciliationCheck,
    HealthCheckResult,
    HealthMonitor,
    HealthStatus,
    RuntimeMetricsLogger,
    validate_live_account,
    validate_live_safety_config,
    validate_order_request_safety,
)
from qts.portfolio import DefaultPortfolio

from .market_data import resolve_event_market_data_provider


class LiveEngine:
    """Live runtime scaffold guarded by explicit safety gates.

    Phase 8 intentionally supports safe initialization, monitoring, dry-run
    broker checks, and order safety validation. Continuous live market-data
    loops and real live broker submission remain disabled by default.
    """

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        brokerage: Brokerage | None = None,
        portfolio: DefaultPortfolio | None = None,
        health_monitor: HealthMonitor | None = None,
        alert_manager: AlertManager | None = None,
        metrics_logger: RuntimeMetricsLogger | None = None,
        clock: RealClock | None = None,
    ) -> None:
        self.config = runtime_config
        self.brokerage = brokerage
        self.portfolio = portfolio
        self.health_monitor = health_monitor
        self.alert_manager = alert_manager or AlertManager()
        self.metrics_logger = metrics_logger or RuntimeMetricsLogger()
        self.clock = clock or RealClock()
        self._running = False
        self._initialized = False
        self.market_data_provider_name: str | None = None
        self._last_reconciliation: dict[str, object] | None = None
        self._last_market_event: Bar | Quote | None = None

    def initialize(self, runtime_config: RuntimeConfig | None = None) -> None:
        if runtime_config is not None:
            self.config = runtime_config
        if self.config.runtime_mode != RuntimeMode.LIVE:
            raise ConfigurationError("LiveEngine requires LIVE runtime mode")

        self.market_data_provider_name = resolve_event_market_data_provider(
            self.config,
            engine_name="LiveEngine",
        )
        policy = validate_live_safety_config(self.config)
        if self.brokerage is None:
            if not policy.dry_run:
                raise LiveSafetyError("real live brokerage submission is not enabled in Phase 8")
            self.brokerage = _DryRunLiveBrokerage(self.config.broker)

        self.brokerage.connect(self.config.broker)
        account = self.brokerage.get_account()
        validate_live_account(self.config, account)

        if self.portfolio is None:
            self.portfolio = DefaultPortfolio(
                account.cash,
                currency=account.currency,
                account_id=account.account_id or "live",
                timestamp=account.timestamp,
            )
        reconciliation_check = BrokerReconciliationCheck(self.portfolio, self.brokerage)
        reconciliation = reconciliation_check.run()
        self._last_reconciliation = dict(reconciliation.details)
        if reconciliation.status == HealthStatus.CRITICAL:
            self.alert_manager.emit(
                AlertSeverity.CRITICAL,
                "live_engine",
                "initial live reconciliation mismatch",
                details=reconciliation.details,
            )
            raise ReconciliationError("initial live reconciliation mismatch")

        self.health_monitor = self.health_monitor or HealthMonitor(
            [
                BrokerConnectionHealthCheck(self.brokerage, clock=self.clock),
                reconciliation_check,
            ]
        )
        self.metrics_logger.increment("live_engine_initializations_total")
        self._initialized = True

    def start(self, *, max_events: int = 0) -> dict[str, object]:
        if not self._initialized:
            self.initialize()
        validate_live_safety_config(self.config)
        self._running = True
        self.metrics_logger.increment("live_engine_starts_total")
        if max_events > 0:
            raise ConfigurationError("continuous live market-data loops are not implemented in Phase 8")
        return self.health_check()

    def stop(self, reason: str | None = None) -> None:
        if self.brokerage is not None:
            self.brokerage.disconnect()
        self._running = False
        self.metrics_logger.increment("live_engine_stops_total")
        if reason:
            self.alert_manager.emit(
                AlertSeverity.WARNING,
                "live_engine",
                f"live engine stopped: {reason}",
                details={"reason": reason},
            )

    def on_market_event(self, event: Bar | Quote) -> dict[str, object]:
        self._require_initialized()
        self._last_market_event = event
        self.metrics_logger.increment("live_market_events_total", tags={"symbol": event.symbol})
        return self.health_check()

    def on_broker_event(self, event: Order | Fill | Account | Position) -> None:
        self._require_initialized()
        event_type = type(event).__name__
        self.metrics_logger.increment("live_broker_events_total", tags={"event_type": event_type})

    def validate_order_request(
        self,
        order_request: OrderRequest,
        *,
        price: float | None = None,
    ) -> bool:
        return validate_order_request_safety(self.config, order_request, price=price)

    def health_check(self) -> dict[str, object]:
        if not self._initialized or self.health_monitor is None:
            return {
                "run_id": self.config.run_id,
                "initialized": self._initialized,
                "running": self._running,
                "status": HealthStatus.CRITICAL.value,
                "healthy": False,
                "checks": [
                    HealthCheckResult(
                        "live_engine_initialized",
                        HealthStatus.CRITICAL,
                        "live engine is not initialized",
                    ).to_dict()
                ],
            }
        summary = self.health_monitor.summary()
        summary.update(
            {
                "run_id": self.config.run_id,
                "initialized": self._initialized,
                "running": self._running,
                "dry_run": bool(self.config.broker.safety.get("dry_run")),
                "market_data_provider": self.market_data_provider_name,
                "last_reconciliation": self._last_reconciliation,
                "last_market_event_symbol": (
                    self._last_market_event.symbol if self._last_market_event is not None else None
                ),
            }
        )
        return summary

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ConfigurationError("live engine must be initialized first")


class _DryRunLiveBrokerage:
    """Dry-run brokerage used only for guarded live initialization tests."""

    def __init__(self, broker_config: BrokerConfig) -> None:
        self.broker_config = broker_config
        self.connected = False
        safety = dict(broker_config.safety)
        account_id = broker_config.account_id or str(safety.get("dry_run_account_id") or "dry-run-live")
        timestamp = datetime.now(timezone.utc)
        self.account = Account(
            account_id=account_id,
            timestamp=timestamp,
            currency="USD",
            cash=float(safety.get("dry_run_cash", 100000.0)),
            equity=float(safety.get("dry_run_equity", safety.get("dry_run_cash", 100000.0))),
            buying_power=float(safety.get("dry_run_buying_power", safety.get("dry_run_cash", 100000.0))),
            gross_exposure=0.0,
            net_exposure=0.0,
            metadata={"dry_run": True},
        )
        self.orders: dict[str, Order] = {}

    def connect(self, broker_config: BrokerConfig | None = None) -> None:
        if broker_config is not None:
            self.broker_config = broker_config
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def submit_order(self, order_request: OrderRequest) -> Order:
        raise LiveSafetyError("dry-run live brokerage never submits orders")

    def cancel_order(self, order_id: str) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise LiveSafetyError(f"unknown dry-run order: {order_id}")
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def list_orders(
        self,
        status: OrderStatus | str | None = None,
        symbol: str | None = None,
    ) -> list[Order]:
        return []

    def get_account(self) -> Account:
        self._require_connected()
        return self.account

    def get_positions(self) -> list[Position]:
        self._require_connected()
        return []

    def poll_fills(self, since: datetime | None = None) -> list[Fill]:
        self._require_connected()
        return []

    def is_market_open(self, timestamp: datetime) -> bool:
        self._require_connected()
        return timestamp.weekday() < 5

    def _require_connected(self) -> None:
        if not self.connected:
            raise LiveSafetyError("dry-run live brokerage is not connected")


__all__ = ["LiveEngine"]
