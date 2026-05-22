"""Paper trading runtime orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from qts.brokers.alpaca import AlpacaBrokerage
from qts.core import ConfigurationError, RealClock
from qts.domain import (
    Bar,
    FeatureFrame,
    Fill,
    Order,
    Quote,
    RiskDecisionStatus,
    RuntimeConfig,
    RuntimeMode,
    StrategyConfig,
    normalize_symbol,
    normalize_timestamp,
)
from qts.execution import ExecutionEngine, OrderRouter
from qts.features import FeaturePipeline, FeatureSpec
from qts.portfolio import DefaultPortfolio
from qts.risk import RiskEngine
from qts.strategies import BaseStrategy, create_strategy


class PaperTradingEngine:
    """Wire Alpaca paper brokerage into the shared strategy/risk/execution path."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        brokerage: AlpacaBrokerage | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        strategies: Sequence[BaseStrategy] | None = None,
        clock: RealClock | None = None,
    ) -> None:
        self.config = runtime_config
        self.brokerage = brokerage
        self.feature_pipeline = feature_pipeline
        self.strategies = list(strategies or [])
        self.clock = clock or RealClock()
        self.data_portal = _PaperDataPortal()
        self.portfolio: DefaultPortfolio | None = None
        self.risk_engine: RiskEngine | None = None
        self.execution_engine: ExecutionEngine | None = None
        self._latest_prices: dict[str, float] = {}
        self._processed_fill_ids: set[str] = set()
        self._last_reconciliation: dict[str, object] | None = None
        self._running = False
        self._initialized = False

    def initialize(self, runtime_config: RuntimeConfig | None = None) -> None:
        if runtime_config is not None:
            self.config = runtime_config
        if self.config.runtime_mode != RuntimeMode.PAPER:
            raise ConfigurationError("PaperTradingEngine requires PAPER runtime mode")
        self.feature_pipeline = self.feature_pipeline or FeaturePipeline(
            _feature_specs_from_strategies(self.config.strategies)
        )
        self.data_portal.feature_pipeline = self.feature_pipeline
        self.brokerage = self.brokerage or AlpacaBrokerage(self.config.broker)
        self.brokerage.connect(self.config.broker)

        broker_account = self.brokerage.get_account()
        broker_positions = self.brokerage.get_positions()
        self.portfolio = DefaultPortfolio(
            broker_account.cash,
            currency=broker_account.currency,
            account_id=broker_account.account_id or "alpaca-paper",
            timestamp=broker_account.timestamp,
        )
        self._last_reconciliation = self.portfolio.reconcile(broker_account, broker_positions)
        self.risk_engine = RiskEngine(self.config.risk)
        self.execution_engine = ExecutionEngine(OrderRouter(self.brokerage))
        if not self.strategies:
            self.strategies = [
                create_strategy(strategy_config)
                for strategy_config in self.config.strategies
                if strategy_config.enabled
            ]
        for strategy, strategy_config in zip(
            self.strategies,
            [config for config in self.config.strategies if config.enabled],
            strict=False,
        ):
            strategy.initialize(strategy_config, self.data_portal, {"runtime_config": self.config})
        self._initialized = True

    def start(self, *, max_events: int = 0) -> dict[str, object]:
        """Start the paper engine.

        Phase 6 provides an initialization and event-handling runtime path. A
        continuous live market-data loop is intentionally deferred until a live
        market data provider is introduced.
        """
        if not self._initialized:
            self.initialize()
        self._running = True
        if max_events <= 0:
            return self.health_check()
        raise ConfigurationError("continuous paper market-data loops are not implemented in Phase 6")

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

    def on_broker_event(self, event: Order | Fill) -> None:
        self._require_initialized()
        assert self.execution_engine is not None
        if isinstance(event, Order):
            self.execution_engine.on_order_update(event)
            return
        self.execution_engine.on_fill(event)
        self._apply_fill(event)

    def poll_broker_updates(self, since: datetime | None = None) -> list[Fill]:
        self._require_initialized()
        assert self.execution_engine is not None
        fills = self.execution_engine.order_router.poll_updates(since)
        for fill in fills:
            if fill.fill_id not in self._processed_fill_ids:
                self.execution_engine.on_fill(fill)
                self._apply_fill(fill)
        return fills

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
            market_open = self.brokerage.is_market_open(self.clock.now())
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
            "mock_mode": bool(self.config.broker.safety.get("mock_mode")),
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


def _feature_specs_from_strategies(strategy_configs: Sequence[StrategyConfig]) -> list[FeatureSpec]:
    specs: list[FeatureSpec] = []
    seen: set[tuple[str, tuple[tuple[str, int | float], ...]]] = set()
    for config in strategy_configs:
        if not config.enabled:
            continue
        strategy_type = config.strategy_type.lower()
        parameters = dict(config.parameters)
        if strategy_type in {"sma_crossover", "sma_cross"}:
            candidates = [
                FeatureSpec("sma", {"window": int(parameters.get("fast_window", 20))}),
                FeatureSpec("sma", {"window": int(parameters.get("slow_window", 50))}),
            ]
        elif strategy_type in {"rsi_mean_reversion", "rsi_reversion"}:
            candidates = [FeatureSpec("rsi", {"window": int(parameters.get("window", 14))})]
        else:
            candidates = []
        for spec in candidates:
            key = (spec.name, tuple(sorted(spec.parameters.items())))
            if key not in seen:
                specs.append(spec)
                seen.add(key)
    return specs


__all__ = ["PaperTradingEngine"]
