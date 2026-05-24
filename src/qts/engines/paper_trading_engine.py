"""Paper trading runtime orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from qts.brokers import AlpacaBrokerage, Brokerage, IBKRBrokerage
from qts.calendar import MarketSessionService, build_market_session_service
from qts.core import Clock, ConfigurationError, RealClock
from qts.domain import (
    Bar,
    BrokerEvent,
    BrokerEventType,
    FeatureFrame,
    Fill,
    Order,
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
    ExecutionEngine,
    OrderRouter,
)
from qts.execution.events import broker_event_from_fill, broker_event_from_order
from qts.features import FeaturePipeline
from qts.market_data import AlpacaStreamClient, alpaca_stream_event_source_from_config
from qts.portfolio import DefaultPortfolio
from qts.risk import RiskEngine
from qts.strategies import BaseStrategy, create_strategy

from .event_loop import (
    MarketEventSource,
    MarketEventSourceFactory,
    RuntimeEventLoop,
    event_source_from_market_data_config,
    heartbeat_policy_from_market_data_config,
    reconnect_policy_from_market_data_config,
)
from .features import feature_pipeline_settings_from_strategies
from .market_data import resolve_event_market_data_provider


class PaperTradingEngine:
    """Wire paper brokerage into the shared strategy/risk/execution path."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        brokerage: Brokerage | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        strategies: Sequence[BaseStrategy] | None = None,
        market_event_source: MarketEventSource | None = None,
        market_event_source_factory: MarketEventSourceFactory | None = None,
        market_stream_client: AlpacaStreamClient | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = runtime_config
        self.brokerage = brokerage
        self.feature_pipeline = feature_pipeline
        self.strategies = list(strategies or [])
        self._strategies_injected = strategies is not None
        self.market_event_source = market_event_source
        self.market_event_source_factory = market_event_source_factory
        self.market_stream_client = market_stream_client
        self.clock = clock or RealClock()
        self.session_service: MarketSessionService | None = None
        self.data_portal = _PaperDataPortal()
        self.market_data_provider_name: str | None = None
        self.portfolio: DefaultPortfolio | None = None
        self.risk_engine: RiskEngine | None = None
        self.execution_engine: ExecutionEngine | None = None
        self._latest_prices: dict[str, float] = {}
        self._processed_fill_ids: set[str] = set()
        self._last_reconciliation: dict[str, object] | None = None
        self._broker_event_checkpoint = BrokerEventSyncCheckpoint()
        self._last_broker_event_sync: dict[str, object] | None = None
        self._running = False
        self._initialized = False

    def initialize(self, runtime_config: RuntimeConfig | None = None) -> None:
        if runtime_config is not None:
            self.config = runtime_config
        if self.config.runtime_mode != RuntimeMode.PAPER:
            raise ConfigurationError("PaperTradingEngine requires PAPER runtime mode")
        self.session_service = build_market_session_service(self.config)
        self.market_data_provider_name = resolve_event_market_data_provider(
            self.config,
            engine_name="PaperTradingEngine",
        )
        if self.market_data_provider_name == "fake_stream" and self.market_event_source is None:
            self.market_event_source = event_source_from_market_data_config(self.config.market_data)
        if (
            self.market_data_provider_name
            in {"alpaca_stream", "alpaca_sip_stream", "alpaca_iex_stream"}
            and self.market_event_source is None
        ):
            self.market_event_source = self._build_alpaca_stream_event_source()
            if self.market_event_source_factory is None and self.market_stream_client is None:
                self.market_event_source_factory = self._build_alpaca_stream_event_source
        if self.feature_pipeline is None:
            feature_specs, schema_version = feature_pipeline_settings_from_strategies(
                self.config.strategies
            )
            self.feature_pipeline = FeaturePipeline(
                feature_specs,
                schema_version=schema_version,
            )
        self.data_portal.feature_pipeline = self.feature_pipeline
        self.brokerage = self.brokerage or _paper_brokerage_from_config(self.config)
        self.brokerage.connect(self.config.broker)

        broker_account = self.brokerage.get_account()
        broker_positions = self.brokerage.get_positions()
        self.portfolio = DefaultPortfolio(
            broker_account.cash,
            currency=broker_account.currency,
            account_id=broker_account.account_id or f"{self.config.broker.broker_type}-account",
            timestamp=broker_account.timestamp,
        )
        self._last_reconciliation = self.portfolio.reconcile(broker_account, broker_positions)
        self.risk_engine = RiskEngine(self.config.risk)
        self.execution_engine = ExecutionEngine(
            OrderRouter(self.brokerage),
            allow_fractional=bool(self.config.execution.get("allow_fractional", True)),
        )
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
        self._initialized = True

    def start(self, *, max_events: int = 0) -> dict[str, object]:
        """Start the paper engine.

        Phase B supports finite fake streams and mockable Alpaca stream adapter
        runs for deterministic paper testing.
        """
        if not self._initialized:
            self.initialize()
        self._running = True
        if max_events < 0:
            raise ConfigurationError("max_events must be non-negative")
        if max_events == 0:
            return self.health_check()
        if self.market_event_source is None:
            raise ConfigurationError(
                "paper runtime event loop requires a streaming market-data provider "
                "or an injected market_event_source"
            )
        loop = RuntimeEventLoop(
            self.market_event_source,
            self.on_market_event,
            source_factory=self.market_event_source_factory,
            session_service=self.session_service,
            clock=self.clock,
            max_staleness_seconds=self.config.market_data.get("max_staleness_seconds"),
            reconnect_policy=reconnect_policy_from_market_data_config(self.config.market_data),
            heartbeat_policy=heartbeat_policy_from_market_data_config(self.config.market_data),
            session_filter_enabled=bool(self.config.market_data.get("session_filter", True)),
            fail_on_out_of_order=bool(self.config.market_data.get("fail_on_out_of_order", True)),
            deduplicate=bool(self.config.market_data.get("deduplicate", True)),
        )
        result = loop.run(max_events=max_events)
        status = self.health_check()
        status["event_loop"] = result.to_dict()
        return status

    def stop(self, reason: str | None = None) -> None:
        if self.brokerage is not None:
            self.brokerage.disconnect()
        self._running = False

    def on_market_event(self, market_event: Bar | Quote) -> list[Order]:
        """Handle one externally supplied paper market event."""
        self._require_initialized()
        assert self.portfolio is not None
        assert self.risk_engine is not None
        assert self.execution_engine is not None
        assert self.feature_pipeline is not None

        self.data_portal.advance(market_event)
        current_price = _event_price(market_event)
        self._latest_prices[market_event.symbol] = current_price
        snapshot = self.portfolio.mark_to_market(self._latest_prices, market_event.timestamp)
        if isinstance(market_event, Quote):
            return []

        features = self.feature_pipeline.update_online(market_event)
        submitted_orders: list[Order] = []
        for strategy in self.strategies:
            if market_event.symbol not in strategy.symbols:
                continue
            outputs = strategy.on_data(market_event, features, snapshot)
            for output in outputs:
                decision = self.risk_engine.evaluate(
                    output,
                    snapshot,
                    {
                        "timestamp": market_event.timestamp,
                        "bar": market_event,
                        "current_bar": market_event,
                        "price": market_event.close,
                        "prices": dict(self._latest_prices),
                    },
                )
                if decision.status != RiskDecisionStatus.REJECTED:
                    submitted_orders.append(self.execution_engine.submit(decision))
        self.poll_broker_updates()
        return submitted_orders

    def on_broker_event(self, event: BrokerEvent | Order | Fill) -> None:
        self._require_initialized()
        assert self.execution_engine is not None
        if isinstance(event, Order):
            event = broker_event_from_order(event, source="paper_external")
        elif isinstance(event, Fill):
            event = broker_event_from_fill(event, source="paper_external")
        self.execution_engine.on_broker_event(event)
        if event.event_type == BrokerEventType.FILL and event.fill is not None:
            self._apply_fill(event.fill)

    def poll_broker_updates(self, since: datetime | None = None) -> list[Fill]:
        self._require_initialized()
        assert self.execution_engine is not None
        events = self.execution_engine.poll_broker_events(since)
        fills: list[Fill] = []
        for event in events:
            if event.event_type == BrokerEventType.FILL and event.fill is not None:
                fills.append(event.fill)
                self._apply_fill(event.fill)
        return fills

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
        """Synchronize a broker-event source through restart-safe checkpoints."""
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
        return dict(self._last_broker_event_sync)

    def reconcile(self) -> dict[str, object]:
        self._require_initialized()
        assert self.portfolio is not None
        assert self.brokerage is not None
        self._last_reconciliation = self.portfolio.reconcile(
            self.brokerage.get_account(),
            self.brokerage.get_positions(),
        )
        return self._last_reconciliation

    def health_check(self) -> dict[str, object]:
        self._require_initialized()
        assert self.brokerage is not None
        healthy = True
        error: str | None = None
        market_open = False
        try:
            market_open = (
                self.session_service.is_tradable(self.clock.now())
                if self.session_service is not None
                else self.brokerage.is_market_open(self.clock.now())
            )
        except Exception as exc:  # pragma: no cover - defensive status reporting
            healthy = False
            error = str(exc)
        return {
            "run_id": self.config.run_id,
            "initialized": self._initialized,
            "running": self._running,
            "healthy": healthy,
            "error": error,
            "market_open": market_open,
            "reconciliation": self._last_reconciliation,
            "broker_event_sync": self._last_broker_event_sync,
            "mock_mode": bool(self.config.broker.safety.get("mock_mode")),
            "market_data_provider": self.market_data_provider_name,
        }

    def _apply_fill(self, fill: Fill) -> None:
        assert self.portfolio is not None
        assert self.brokerage is not None
        assert self.risk_engine is not None
        if fill.fill_id in self._processed_fill_ids:
            return
        self._processed_fill_ids.add(fill.fill_id)
        order = self.brokerage.get_order(fill.order_id)
        snapshot = self.portfolio.apply_fill(fill, order)
        for strategy in self.strategies:
            if fill.symbol in strategy.symbols:
                strategy.on_fill(fill)
        self.risk_engine.update_after_fill(fill, snapshot)

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ConfigurationError("paper trading engine must be initialized first")

    def _build_alpaca_stream_event_source(self) -> MarketEventSource:
        return alpaca_stream_event_source_from_config(
            self.config,
            client=self.market_stream_client,
        )


class _PaperDataPortal:
    """Minimal live data portal for externally supplied paper events."""

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
            raise ConfigurationError("paper data portal has no feature pipeline")
        bars = [bar for bar in self._bars if bar.symbol in {symbol.upper() for symbol in symbols}]
        if lookback is not None:
            bars = bars[-lookback:]
        return self.feature_pipeline.transform_batch(bars)

    def advance(self, market_event: Bar | Quote) -> None:
        symbol = market_event.symbol
        if isinstance(market_event, Bar):
            self._bars.append(market_event)
            self._current_bars[symbol] = market_event
        else:
            self._quotes[symbol] = market_event


def _event_price(market_event: Bar | Quote) -> float:
    if isinstance(market_event, Quote):
        return (market_event.bid_price + market_event.ask_price) / 2.0
    return market_event.close


def _paper_brokerage_from_config(config: RuntimeConfig) -> Brokerage:
    broker_type = config.broker.broker_type.lower()
    if config.broker.paper is False:
        raise ConfigurationError("PaperTradingEngine requires a paper broker configuration")
    if broker_type == "alpaca_paper":
        return AlpacaBrokerage(config.broker)
    if broker_type == "ibkr_paper":
        return IBKRBrokerage(config.broker)
    raise ConfigurationError(
        "PaperTradingEngine currently supports broker.broker_type=alpaca_paper or ibkr_paper"
    )


__all__ = ["PaperTradingEngine"]
