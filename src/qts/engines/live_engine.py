"""Guarded live-trading engine scaffold."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from qts.brokers.alpaca import AlpacaBrokerage
from qts.brokers.interfaces import Brokerage
from qts.calendar import MarketSessionService, build_market_session_service, default_market_session_service
from qts.core import ConfigurationError, ExecutionError, LiveSafetyError, RealClock, ReconciliationError
from qts.domain import (
    Account,
    Bar,
    BrokerEvent,
    BrokerConfig,
    FeatureFrame,
    Fill,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    Quote,
    RiskDecisionStatus,
    RuntimeConfig,
    RuntimeMode,
    normalize_symbol,
    normalize_timestamp,
)
from qts.execution import (
    BrokerEventSource,
    BrokerEventSyncCheckpoint,
    BrokerEventSyncLoop,
    BrokerEventSyncPolicy,
    broker_event_from_account,
    broker_event_from_fill,
    broker_event_from_order,
    broker_event_from_position,
    build_order_request,
)
from qts.features import FeaturePipeline
from qts.ml import collect_strategy_ml_diagnostics
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
    validate_live_automated_submission_config,
    validate_live_order_submission_config,
    validate_live_safety_config,
    validate_order_request_safety,
)
from qts.portfolio import DefaultPortfolio
from qts.risk import RiskEngine
from qts.strategies import BaseStrategy, create_strategy

from .decision_pipeline import RuntimeDecisionPipeline, RuntimeDecisionResult
from .features import feature_pipeline_settings_from_strategies
from .market_data import resolve_event_market_data_provider


class LiveEngine:
    """Live runtime scaffold guarded by explicit safety gates.

    The live engine supports safe initialization, monitoring, dry-run previews,
    manual submission, and separately gated automated preview submission.
    Continuous live market-data loops remain disabled by default.
    """

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        brokerage: Brokerage | None = None,
        portfolio: DefaultPortfolio | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        strategies: Sequence[BaseStrategy] | None = None,
        health_monitor: HealthMonitor | None = None,
        alert_manager: AlertManager | None = None,
        metrics_logger: RuntimeMetricsLogger | None = None,
        clock: RealClock | None = None,
    ) -> None:
        self.config = runtime_config
        self.brokerage = brokerage
        self.portfolio = portfolio
        self.feature_pipeline = feature_pipeline
        self.strategies = list(strategies or [])
        self._strategies_injected = strategies is not None
        self.health_monitor = health_monitor
        self.alert_manager = alert_manager or AlertManager()
        self.metrics_logger = metrics_logger or RuntimeMetricsLogger()
        self.clock = clock or RealClock()
        self.session_service: MarketSessionService | None = None
        self.data_portal = _LiveDataPortal()
        self.risk_engine: RiskEngine | None = None
        self.decision_pipeline: RuntimeDecisionPipeline | None = None
        self._running = False
        self._initialized = False
        self.market_data_provider_name: str | None = None
        self._last_reconciliation: dict[str, object] | None = None
        self._last_market_event: Bar | Quote | None = None
        self._latest_prices: dict[str, float] = {}
        self._decision_previews: list[dict[str, object]] = []
        self._broker_event_checkpoint = BrokerEventSyncCheckpoint()
        self._last_broker_event_sync: dict[str, object] | None = None
        self._live_order_submissions: list[dict[str, object]] = []
        self._last_live_order_submission: dict[str, object] | None = None
        self._automated_submission_events: list[dict[str, object]] = []
        self._last_automated_submission_event: dict[str, object] | None = None
        self._automated_submission_stopped = False
        self._automated_submission_stop_reason: str | None = None

    def initialize(self, runtime_config: RuntimeConfig | None = None) -> None:
        if runtime_config is not None:
            self.config = runtime_config
        if self.config.runtime_mode != RuntimeMode.LIVE:
            raise ConfigurationError("LiveEngine requires LIVE runtime mode")
        self.session_service = build_market_session_service(self.config)

        self.market_data_provider_name = resolve_event_market_data_provider(
            self.config,
            engine_name="LiveEngine",
        )
        policy = validate_live_safety_config(self.config)
        if self.brokerage is None:
            if policy.dry_run:
                self.brokerage = _DryRunLiveBrokerage(self.config.broker)
            else:
                validate_live_order_submission_config(self.config)
                self.brokerage = _live_brokerage_from_config(self.config)

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
        if self.feature_pipeline is None:
            feature_specs, schema_version = feature_pipeline_settings_from_strategies(
                self.config.strategies
            )
            self.feature_pipeline = FeaturePipeline(feature_specs, schema_version=schema_version)
        self.data_portal.feature_pipeline = self.feature_pipeline
        self.risk_engine = RiskEngine(self.config.risk)
        enabled_strategy_configs = [config for config in self.config.strategies if config.enabled]
        if self._strategies_injected and len(self.strategies) != len(enabled_strategy_configs):
            raise ConfigurationError(
                "injected strategy count does not match enabled strategy config count"
            )
        if not self._strategies_injected:
            self.strategies = [
                create_strategy(strategy_config)
                for strategy_config in enabled_strategy_configs
            ]
        for strategy, strategy_config in zip(
            self.strategies,
            enabled_strategy_configs,
            strict=True,
        ):
            strategy.initialize(strategy_config, self.data_portal, {"runtime_config": self.config})
        self._latest_prices.clear()
        self.decision_pipeline = RuntimeDecisionPipeline(
            runtime_config=self.config,
            data_portal=self.data_portal,
            portfolio=self.portfolio,
            feature_pipeline=self.feature_pipeline,
            risk_engine=self.risk_engine,
            strategies=self.strategies,
            session_service=self.session_service,
            latest_prices=self._latest_prices,
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
                BrokerConnectionHealthCheck(
                    self.brokerage,
                    clock=self.clock,
                    market_session_service=self.session_service,
                ),
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
            raise ConfigurationError("continuous live market-data loops are not implemented")
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
        assert self.decision_pipeline is not None
        self._last_market_event = event
        self.metrics_logger.increment("live_market_events_total", tags={"symbol": event.symbol})
        result = self.decision_pipeline.on_market_event(event)
        previews = [] if isinstance(event, Quote) else self._preview_bar_decisions(result)
        status = self.health_check()
        status["decision_previews"] = previews
        return status

    def on_broker_event(self, event: BrokerEvent | Order | Fill | Account | Position) -> None:
        self._require_initialized()
        if isinstance(event, Order):
            event = broker_event_from_order(event, source="live_external")
        elif isinstance(event, Fill):
            event = broker_event_from_fill(event, source="live_external")
        elif isinstance(event, Account):
            event = broker_event_from_account(event, source="live_external")
        elif isinstance(event, Position):
            event = broker_event_from_position(event, source="live_external")
        event_type = event.event_type.value if isinstance(event, BrokerEvent) else type(event).__name__
        self.metrics_logger.increment("live_broker_events_total", tags={"event_type": event_type})

    def sync_broker_events(
        self,
        source: BrokerEventSource,
        *,
        max_events: int = 0,
        max_gap_seconds: float | int | None = None,
        fail_on_gap: bool = True,
        fail_on_out_of_order: bool = True,
        reconcile_before: bool = True,
        reconcile_after: bool = True,
    ) -> dict[str, object]:
        """Synchronize broker lifecycle events without enabling live submission."""
        self._require_initialized()
        reconciliation_before = self.reconcile() if reconcile_before else None
        loop = BrokerEventSyncLoop(
            source,
            self.on_broker_event,
            checkpoint=self._broker_event_checkpoint,
            policy=BrokerEventSyncPolicy(
                max_gap_seconds=None if max_gap_seconds is None else float(max_gap_seconds),
                fail_on_gap=fail_on_gap,
                fail_on_out_of_order=fail_on_out_of_order,
            ),
        )
        result = loop.run(max_events=max_events)
        reconciliation_after = self.reconcile() if reconcile_after else None
        self._last_broker_event_sync = result.to_dict()
        self._last_broker_event_sync["checkpoint"] = self._broker_event_checkpoint.to_dict()
        self._last_broker_event_sync["reconciliation_before"] = reconciliation_before
        self._last_broker_event_sync["reconciliation_after"] = reconciliation_after
        self.metrics_logger.increment(
            "live_broker_event_sync_runs_total",
            tags={"stopped_reason": str(result.stopped_reason)},
        )
        return dict(self._last_broker_event_sync)

    def reconcile(self) -> dict[str, object]:
        self._require_initialized()
        assert self.portfolio is not None
        assert self.brokerage is not None
        check = BrokerReconciliationCheck(self.portfolio, self.brokerage)
        result = check.run()
        self._last_reconciliation = dict(result.details)
        if result.status == HealthStatus.CRITICAL:
            self.alert_manager.emit(
                AlertSeverity.CRITICAL,
                "live_engine",
                "live reconciliation mismatch",
                details=result.details,
            )
        return self._last_reconciliation

    def validate_order_request(
        self,
        order_request: OrderRequest,
        *,
        price: float | None = None,
    ) -> bool:
        return validate_order_request_safety(self.config, order_request, price=price)

    def submit_live_order(
        self,
        order_request: OrderRequest,
        *,
        price: float | None = None,
        require_reconciliation: bool = True,
    ) -> dict[str, object]:
        """Submit one manually supplied live order through explicit safety gates."""
        self._require_initialized()
        assert self.brokerage is not None
        policy = validate_live_order_submission_config(self.config)
        validate_order_request_safety(self.config, order_request, price=price)
        validate_live_account(self.config, self.brokerage.get_account())
        reconciliation = self.reconcile() if require_reconciliation else None
        if reconciliation is not None and not bool(reconciliation.get("matched")):
            raise ReconciliationError("live order submission blocked by reconciliation mismatch")

        try:
            order = self.brokerage.submit_order(order_request)
        except Exception:
            self.metrics_logger.increment("live_order_submission_failures_total")
            raise

        self.on_broker_event(order)
        payload: dict[str, object] = {
            "submitted": True,
            "dry_run": policy.dry_run,
            "order_id": order.order_id,
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "status": order.status.value,
            "order": order.to_dict(),
            "reconciliation": reconciliation,
        }
        self._last_live_order_submission = payload
        self._live_order_submissions.append(payload)
        self.metrics_logger.increment(
            "live_order_submissions_total",
            tags={"symbol": order.symbol, "status": order.status.value},
        )
        return dict(payload)

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
                "broker_event_sync": self._last_broker_event_sync,
                "live_order_submission_count": len(self._live_order_submissions),
                "last_live_order_submission": self._last_live_order_submission,
                "automated_submission_enabled": _truthy(
                    self.config.broker.safety.get("enable_automated_submission")
                ),
                "automated_submission_kill_switch": _truthy(
                    self.config.broker.safety.get("automated_submission_kill_switch")
                ),
                "automated_submission_count": len(
                    [
                        event
                        for event in self._automated_submission_events
                        if event.get("automation_status") == "submitted"
                    ]
                ),
                "automated_submission_event_count": len(self._automated_submission_events),
                "last_automated_submission_event": self._last_automated_submission_event,
                "automated_submission_stopped": self._automated_submission_stopped,
                "automated_submission_stop_reason": self._automated_submission_stop_reason,
                "last_market_event_symbol": (
                    self._last_market_event.symbol if self._last_market_event is not None else None
                ),
                "ml_models": collect_strategy_ml_diagnostics(self.strategies),
                "decision_preview_count": len(self._decision_previews),
                "last_decision_preview": (
                    self._decision_previews[-1] if self._decision_previews else None
                ),
            }
        )
        if self._automated_submission_stopped:
            summary["status"] = HealthStatus.CRITICAL.value
            summary["healthy"] = False
            checks = list(summary.get("checks") or [])
            checks.append(
                HealthCheckResult(
                    "live_automated_submission",
                    HealthStatus.CRITICAL,
                    "automated live submission is stopped",
                    details={"reason": self._automated_submission_stop_reason},
                ).to_dict()
            )
            summary["checks"] = checks
        return summary

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ConfigurationError("live engine must be initialized first")

    def _preview_bar_decisions(self, result: RuntimeDecisionResult) -> list[dict[str, object]]:
        event = result.market_event
        if not isinstance(event, Bar):
            return []
        previews: list[dict[str, object]] = []
        for decision in result.risk_decisions:
            preview, order_request = self._decision_preview(event, decision)
            if order_request is not None:
                self._maybe_submit_automated_preview(event, preview, order_request)
            previews.append(preview)
            self._decision_previews.append(preview)
            self.metrics_logger.increment(
                "live_decision_previews_total",
                tags={
                    "symbol": event.symbol,
                    "preview_status": str(preview["preview_status"]),
                },
            )
        return previews

    def _decision_preview(
        self,
        event: Bar,
        decision,
    ) -> tuple[dict[str, object], OrderRequest | None]:  # type: ignore[no-untyped-def]
        preview: dict[str, object] = {
            "preview_id": f"preview-{decision.decision_id}",
            "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
            "symbol": event.symbol,
            "risk_decision_id": decision.decision_id,
            "risk_status": decision.status.value,
            "preview_status": "risk_rejected",
            "would_submit": False,
            "reasons": list(decision.reasons),
            "order_request": None,
            "error": None,
            "automation_status": "not_applicable",
            "automation_error": None,
            "submission_result": None,
            "post_submission_reconciliation": None,
        }
        if decision.status == RiskDecisionStatus.REJECTED:
            return preview, None
        try:
            order_request = build_order_request(
                decision,
                allow_fractional=bool(self.config.execution.get("allow_fractional", True)),
                metadata={"live_decision_preview": True},
            )
            preview["order_request"] = order_request.to_dict()
            validate_order_request_safety(self.config, order_request, price=event.close)
        except (ExecutionError, LiveSafetyError) as exc:
            preview["preview_status"] = "safety_rejected"
            preview["error"] = str(exc)
            return preview, None
        preview["preview_status"] = "safety_approved"
        preview["would_submit"] = True
        preview["automation_status"] = "disabled"
        return preview, order_request

    def _maybe_submit_automated_preview(
        self,
        event: Bar,
        preview: dict[str, object],
        order_request: OrderRequest,
    ) -> None:
        if not _truthy(self.config.broker.safety.get("enable_automated_submission")):
            return
        try:
            validate_live_automated_submission_config(self.config)
        except LiveSafetyError as exc:
            self._record_automated_submission_event(
                preview,
                status="blocked",
                error=str(exc),
            )
            return
        if self._automated_submission_stopped:
            self._record_automated_submission_event(
                preview,
                status="blocked",
                error=self._automated_submission_stop_reason
                or "automated live submission is stopped",
            )
            return
        if not self._running:
            self._record_automated_submission_event(
                preview,
                status="blocked",
                error="automated live submission requires the live engine to be running",
            )
            return

        submission_result: dict[str, object] | None = None
        post_reconciliation: dict[str, object] | None = None
        try:
            submission_result = self.submit_live_order(
                order_request,
                price=event.close,
                require_reconciliation=True,
            )
            post_reconciliation = self.reconcile()
            submission_result["post_submission_reconciliation"] = post_reconciliation
            if not bool(post_reconciliation.get("matched")):
                raise ReconciliationError(
                    "automated live submission post-submit reconciliation mismatch"
                )
        except Exception as exc:
            self._stop_automated_submission(
                str(exc),
                preview=preview,
                submission_result=submission_result,
                post_reconciliation=post_reconciliation,
            )
            return

        self._record_automated_submission_event(
            preview,
            status="submitted",
            submission_result=submission_result,
            post_reconciliation=post_reconciliation,
        )
        self.metrics_logger.increment(
            "live_automated_submissions_total",
            tags={"symbol": order_request.symbol},
        )

    def _record_automated_submission_event(
        self,
        preview: dict[str, object],
        *,
        status: str,
        error: str | None = None,
        submission_result: dict[str, object] | None = None,
        post_reconciliation: dict[str, object] | None = None,
    ) -> None:
        preview["automation_status"] = status
        preview["automation_error"] = error
        preview["submission_result"] = submission_result
        preview["post_submission_reconciliation"] = post_reconciliation
        event = {
            "preview_id": preview["preview_id"],
            "symbol": preview["symbol"],
            "automation_status": status,
            "automation_error": error,
            "submission_result": submission_result,
            "post_submission_reconciliation": post_reconciliation,
        }
        self._last_automated_submission_event = event
        self._automated_submission_events.append(event)

    def _stop_automated_submission(
        self,
        reason: str,
        *,
        preview: dict[str, object],
        submission_result: dict[str, object] | None = None,
        post_reconciliation: dict[str, object] | None = None,
    ) -> None:
        self._automated_submission_stopped = True
        self._automated_submission_stop_reason = reason
        self._running = False
        self._record_automated_submission_event(
            preview,
            status="failed",
            error=reason,
            submission_result=submission_result,
            post_reconciliation=post_reconciliation,
        )
        self.metrics_logger.increment("live_automated_submission_failures_total")
        self.alert_manager.emit(
            AlertSeverity.CRITICAL,
            "live_engine",
            "automated live submission stopped",
            details={"reason": reason, "preview_id": preview.get("preview_id")},
        )


class _LiveDataPortal:
    """Minimal data portal for live decision preview."""

    def __init__(self) -> None:
        self._bars: list[Bar] = []
        self._current_bars: dict[str, Bar] = {}
        self._quotes: dict[str, Quote] = {}
        self.feature_pipeline: FeaturePipeline | None = None

    def get_bars(
        self,
        symbol: str,
        lookback: int | None = None,
        end: datetime | str | None = None,
    ) -> list[Bar]:
        normalized_symbol = normalize_symbol(symbol)
        rows = [bar for bar in self._bars if bar.symbol == normalized_symbol]
        if end is not None:
            rows = [bar for bar in rows if bar.timestamp <= normalize_timestamp(end)]
        return rows[-lookback:] if lookback is not None else rows

    def get_current_bar(self, symbol: str) -> Bar | None:
        return self._current_bars.get(normalize_symbol(symbol))

    def get_quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(normalize_symbol(symbol))

    def get_feature_frame(
        self,
        symbols: Sequence[str],
        feature_names: Sequence[str] | None = None,
        lookback: int | None = None,
    ) -> FeatureFrame:
        if self.feature_pipeline is None:
            raise ConfigurationError("live data portal has no feature pipeline")
        bars = [bar for bar in self._bars if bar.symbol in {symbol.upper() for symbol in symbols}]
        if lookback is not None:
            bars = bars[-lookback:]
        frame = self.feature_pipeline.transform_batch(bars)
        return _filter_feature_frame(frame, feature_names)

    def advance(self, event: Bar | Quote) -> None:
        if isinstance(event, Bar):
            self._bars.append(event)
            self._current_bars[event.symbol] = event
            return
        self._quotes[event.symbol] = event


def _filter_feature_frame(
    frame: FeatureFrame,
    feature_names: Sequence[str] | None,
) -> FeatureFrame:
    if feature_names is None:
        return frame
    allowed = set(feature_names)
    rows = [
        {
            key: value
            for key, value in row.items()
            if key in allowed or key in {"symbol", "timestamp"}
        }
        for row in frame.features
    ]
    return FeatureFrame(
        symbols=frame.symbols,
        timestamps=frame.timestamps,
        features=rows,
        schema_version=frame.schema_version,
        generated_at=frame.generated_at,
        source=frame.source,
    )


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _live_brokerage_from_config(config: RuntimeConfig) -> Brokerage:
    broker_type = config.broker.broker_type.lower()
    if broker_type == "alpaca_live":
        return AlpacaBrokerage(config.broker)
    raise ConfigurationError(
        "LiveEngine currently supports broker.broker_type=alpaca_live for non-dry-run live brokerage"
    )


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
        return default_market_session_service().is_tradable(timestamp)

    def _require_connected(self) -> None:
        if not self.connected:
            raise LiveSafetyError("dry-run live brokerage is not connected")


__all__ = ["LiveEngine"]
