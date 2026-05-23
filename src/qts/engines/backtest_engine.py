"""Deterministic bar-driven backtest engine."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from qts.brokers.backtest import BacktestBrokerage
from qts.core import ConfigurationError
from qts.domain import (
    BacktestResult,
    Bar,
    BrokerConfig,
    Fill,
    Order,
    RiskDecisionStatus,
    RuntimeConfig,
)
from qts.execution import ExecutionEngine, OrderRouter
from qts.features import FeaturePipeline
from qts.market_data import CSVBarProvider, LocalParquetProvider, MarketDataProvider
from qts.market_data.portal import DefaultDataPortal
from qts.portfolio import DefaultPortfolio
from qts.reporting import BacktestReporter
from qts.risk import RiskEngine
from qts.strategies import BaseStrategy, create_strategy

from .features import feature_pipeline_settings_from_strategies


class BacktestEngine:
    """Connect Phase 1-4 components into a reproducible bar loop."""

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        *,
        market_data_provider: MarketDataProvider | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        strategies: Sequence[BaseStrategy] | None = None,
        reporter: BacktestReporter | None = None,
    ) -> None:
        self.config = runtime_config
        self.provider = market_data_provider
        self.feature_pipeline = feature_pipeline
        self.strategies = list(strategies or [])
        self.reporter = reporter or BacktestReporter()
        self.data_portal: DefaultDataPortal | None = None
        self.portfolio: DefaultPortfolio | None = None
        self.risk_engine: RiskEngine | None = None
        self.brokerage: BacktestBrokerage | None = None
        self.execution_engine: ExecutionEngine | None = None
        self._latest_prices: dict[str, float] = {}
        self._snapshots = []
        self._initialized = False
        self._result: BacktestResult | None = None

    def initialize(self, runtime_config: RuntimeConfig | None = None) -> None:
        if runtime_config is not None:
            self.config = runtime_config
        self.provider = self.provider or _provider_from_config(self.config)
        if self.feature_pipeline is None:
            feature_specs, schema_version = feature_pipeline_settings_from_strategies(
                self.config.strategies
            )
            self.feature_pipeline = FeaturePipeline(
                feature_specs,
                schema_version=schema_version,
            )
        self.data_portal = DefaultDataPortal(
            self.provider,
            symbols=self.config.symbols,
            start=self.config.start,
            end=self.config.end,
            timeframe=self.config.timeframe,
            feature_pipeline=self.feature_pipeline,
            enforce_replay_bounds=True,
        )
        self.portfolio = DefaultPortfolio(
            float(self.config.portfolio.get("starting_cash", 100000.0)),
            currency=str(self.config.portfolio.get("currency", "USD")),
            account_id=str(self.config.portfolio.get("account_id", "portfolio")),
            timestamp=self.config.start,
        )
        self.risk_engine = RiskEngine(self.config.risk)
        self.brokerage = BacktestBrokerage(
            self.config.broker,
            starting_cash=float(self.config.portfolio.get("starting_cash", 100000.0)),
            currency=str(self.config.portfolio.get("currency", "USD")),
            account_id=self.config.broker.account_id or "backtest",
            fill_policy=self.config.broker.fill_policy,
            commission_model=self.config.broker.commission_model,
            slippage_model=self.config.broker.slippage_model,
        )
        self.brokerage.connect()
        self.execution_engine = ExecutionEngine(
            OrderRouter(self.brokerage),
            allow_fractional=bool(self.config.execution.get("allow_fractional", True)),
        )
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
        self._latest_prices.clear()
        self._snapshots = [self.portfolio.get_account_snapshot()]
        self._initialized = True

    def run(self) -> BacktestResult:
        if not self._initialized:
            self.initialize()
        assert self.provider is not None
        assert self.config.start is not None
        assert self.config.end is not None

        for bar in self.provider.iter_replay(
            self.config.symbols,
            self.config.start,
            self.config.end,
            self.config.timeframe,
        ):
            self.step(bar)
        for strategy in self.strategies:
            strategy.on_end({"runtime_config": self.config})
        self._result = self.finalize()
        return self._result

    def step(self, market_event: Bar) -> None:
        self._require_initialized()
        assert self.data_portal is not None
        assert self.feature_pipeline is not None
        assert self.portfolio is not None
        assert self.risk_engine is not None
        assert self.brokerage is not None
        assert self.execution_engine is not None

        self.data_portal.advance(market_event)
        fills = self.brokerage.on_market_event(market_event)
        self._apply_fills(fills)

        self._latest_prices[market_event.symbol] = market_event.close
        snapshot = self.portfolio.mark_to_market(self._latest_prices, market_event.timestamp)
        features = self.feature_pipeline.update_online(market_event)

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
                    self.execution_engine.submit(decision)
        self._snapshots.append(self.portfolio.mark_to_market(self._latest_prices, market_event.timestamp))

    def finalize(self) -> BacktestResult:
        self._require_initialized()
        assert self.portfolio is not None
        assert self.brokerage is not None
        start_time = self._snapshots[0].timestamp if self._snapshots else self.config.start
        end_time = self._snapshots[-1].timestamp if self._snapshots else self.config.end
        metrics = self.reporter.generate_metrics(
            self._snapshots,
            self.portfolio.get_trade_ledger(),
            self.config,
        )
        result = BacktestResult(
            run_id=self.config.run_id,
            config=self.config,
            start_time=start_time,
            end_time=end_time,
            symbols=self.config.symbols,
            portfolio_snapshots=list(self._snapshots),
            orders=self.brokerage.list_orders(),
            fills=self.brokerage.poll_fills(),
            trade_ledger=self.portfolio.get_trade_ledger(),
            cash_ledger=self.portfolio.get_cash_ledger(),
            metrics=metrics,
            artifacts={},
        )
        output_dir = self.config.reporting.get("output_dir", "artifacts/reports")
        result.artifacts = self.reporter.export_report(result, output_dir)
        return result

    def _apply_fills(self, fills: list[Fill]) -> None:
        assert self.portfolio is not None
        assert self.brokerage is not None
        assert self.execution_engine is not None
        assert self.risk_engine is not None
        for fill in fills:
            order = self.brokerage.get_order(fill.order_id)
            self.execution_engine.on_fill(fill)
            snapshot = self.portfolio.apply_fill(fill, order)
            for strategy in self.strategies:
                if fill.symbol in strategy.symbols:
                    strategy.on_fill(fill)
            self.risk_engine.update_after_fill(fill, snapshot)

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ConfigurationError("backtest engine must be initialized before stepping")


def _provider_from_config(config: RuntimeConfig) -> MarketDataProvider:
    provider_name = str(config.market_data.get("provider", "")).lower()
    path = config.market_data.get("path")
    if not path:
        raise ConfigurationError("market_data.path is required for Phase 5 backtests")
    if provider_name in {"csv", "local_csv", "fixture_csv"}:
        return CSVBarProvider(Path(path))
    if provider_name in {"parquet", "local_parquet"}:
        return LocalParquetProvider(Path(path))
    raise ConfigurationError(f"unsupported Phase 5 market data provider: {provider_name}")


__all__ = ["BacktestEngine"]
