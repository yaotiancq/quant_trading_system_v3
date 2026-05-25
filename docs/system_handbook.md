# Quant Trading System V3 System Handbook

This handbook teaches the repository from the inside out. Use it when you want
to understand the architecture, trace runtime behavior, or make engineering
changes without breaking the project boundaries.

The root documentation remains the source of truth. This handbook is a practical
map of the implemented files and how they fit together.

## 1. Mental Model

The system is built around one invariant:

```text
market data -> features -> strategy -> risk -> execution -> brokerage -> portfolio -> reporting/monitoring
```

Each layer owns a small responsibility:

| Layer | Owns | Must Not Own |
|---|---|---|
| `domain` | Stable data models and enums | I/O, broker calls, strategy logic |
| `core` | Config, clocks, exceptions, logging | Concrete trading behavior |
| `calendar` | Exchange sessions, holidays, early closes, tradability checks | Market data downloads or brokerage state |
| `market_data` | Historical data downloads/loading, replay, strategy data portal | Brokerage state |
| `features` | Reusable indicators and schemas | Strategy-specific decisions |
| `strategies` | Signal generation | Order submission, account mutation |
| `risk` | Sizing and risk approval | Broker API details |
| `execution` | Order request creation, routing, and broker lifecycle synchronization | Vendor clients |
| `brokers` | Normalized brokerage implementations | Market data loading |
| `integrations` | Vendor HTTP clients and payload mapping | Domain business logic |
| `portfolio` | Internal accounting and reconciliation | Strategy decisions |
| `engines` | Runtime orchestration | Detailed strategy/broker/risk logic |
| `reporting` | Backtest metrics and artifacts | Trading decisions |
| `ml` | Offline training and runtime inference helpers | Direct broker interaction |
| `monitoring` | Health, alerts, recovery, live safety | Strategy logic |

## 2. Runtime Flows

### Backtest Flow

1. `scripts/run_backtest.py` loads config.
2. `BacktestEngine` builds a market data provider.
3. `DefaultDataPortal` exposes replay-bounded bars to strategies.
4. `FeaturePipeline` updates features on each bar.
5. Strategies emit `Signal` or `TradeIntent` objects.
6. `RiskEngine` sizes and validates the intent.
7. `ExecutionEngine` builds an `OrderRequest`.
8. `OrderRouter` sends the request to `BacktestBrokerage`.
9. `BacktestBrokerage` simulates fills on market events.
10. Broker order/fill updates can be represented as normalized `BrokerEvent`
    lifecycle events.
11. `DefaultPortfolio` applies fills and records ledgers.
12. `BacktestReporter` writes metrics and artifacts.

### Data Download Flow

1. `scripts/download_data.py` loads `configs/data/alpaca_sip_bars.yaml`.
2. `AlpacaBarDownloadConfig` validates symbols, date range, K-line timeframe,
   local session filter, output format, layout, and partition settings.
3. `AlpacaMarketDataClient` requests paginated Alpaca stock bars.
4. `download_alpaca_bars` normalizes the full API interval, then uses
   `MarketSessionService` to apply regular-session filtering, holidays, and
   early closes.
5. Filtered bars are written as CSV or Parquet rows.
6. Partitioned output is written below directories such as
   `timeframe=1Min/symbol=SPY/date=2024-01-02/`.
7. The resulting dataset can be consumed by `CSVBarProvider` or
   `LocalParquetProvider`, both of which read matching files recursively when
   given a directory.

### Paper Flow

1. `scripts/run_paper_trading.py` loads a paper config.
2. `PaperTradingEngine` validates `PAPER` mode and an event-driven market-data
   provider: `external_events`, `fake_stream`, or mockable `alpaca_stream`.
3. The engine selects `AlpacaBrokerage` or `IBKRBrokerage`.
4. The broker adapter connects to a real or in-memory client.
5. The portfolio reconciles against broker account and positions.
6. Externally supplied `Bar`/`Quote` events, finite fake-stream events, or mock
   Alpaca stream payloads normalized by `qts.market_data.streaming` are
   processed through the same feature, strategy, risk, and execution path.
7. Runtime event-loop status includes disconnect, reconnect,
   heartbeat/data-gap, source-run, and stopped-reason counters.
8. Broker order/fill polling is normalized into `BrokerEvent` lifecycle events
   before execution and portfolio state are synchronized.
9. Alpaca/IBKR push-style broker payloads can be normalized through in-memory
   adapter clients for deterministic boundary tests.
10. `sync_broker_events(...)` can consume any normalized `BrokerEventSource`
   through duplicate, checkpoint, out-of-order, and gap checks, with
   reconciliation before and after the run.

### Live Flow

1. `scripts/run_live_trading.py` loads live config and dry-run overrides.
2. `LiveEngine` validates safety gates.
3. `_DryRunLiveBrokerage` provides account/position scaffolding.
4. Monitoring, reconciliation, and health checks run.
5. Direct live bar events can produce guarded decision previews through
   feature, strategy, risk, order-request construction, and live safety
   validation.
6. Broker-event sync can record lifecycle/reconciliation status.
7. Manual `submit_live_order(...)` calls can submit only after non-dry-run,
   confirmation, submission, account, order, session, and reconciliation gates
   pass.
8. Non-dry-run `LiveEngine` can construct the selected Alpaca live adapter only
   after the same D1 submission gates pass.
9. Safety-approved previews can submit automatically only when
   `enable_automated_submission` is true and the automated kill switch is open.
10. Automated submission failures stop further automation and report critical
    live health.

## 3. File-by-File Reference

The list below covers project files that make up the system contract. Ignored
runtime files such as `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, and
generated egg-info metadata are not part of the source contract.

### Root Files

| File | Purpose |
|---|---|
| `.env.example` | Template for local secrets and endpoint overrides. |
| `.gitignore` | Keeps local secrets, virtualenvs, caches, data, and artifacts out of git. |
| `README.md` | Quick project overview and common commands. |
| `SYSTEM_DESIGN.md` | Architectural goals, module boundaries, flows, and dependency rules. |
| `PHASE_PLAN.md` | Phase-by-phase implementation scope and acceptance criteria. |
| `INTERFACES.md` | Public module contracts and ownership rules. |
| `DATA_MODELS.md` | Stable domain model and enum documentation. |
| `DECISIONS.md` | Architectural decision records. |
| `PROJECT_STATE.md` | Current implementation state, completed phases, known issues, and next task guidance. |
| `CHANGELOG.md` | Phase and documentation change log. |
| `pyproject.toml` | Build metadata, optional dependencies, CLI entry point, pytest, ruff, and mypy config. |

### Documentation Files

| File | Purpose |
|---|---|
| `docs/runbooks.md` | Operational procedures for live-readiness and incident-style workflows. |
| `docs/user_manual.md` | Operator manual for setup, configs, commands, and safe workflows. |
| `docs/system_handbook.md` | This engineering guide and file map. |

### Runtime Directories

| File | Purpose |
|---|---|
| `data/.gitkeep` | Placeholder for local data. Actual data is ignored. |
| `artifacts/.gitkeep` | Placeholder for generated outputs. Actual artifacts are ignored. |

### Configuration Files

| File | Purpose |
|---|---|
| `configs/base.yaml` | Shared defaults: project name, runtime timezone, paths, logging. |
| `configs/backtest.yaml` | Generic partitioned local CSV backtest template using `data/alpaca`, `risk_ref`, and a strategy `config_ref`. |
| `configs/backtest_fixture.yaml` | Fully runnable CSV fixture backtest with referenced snippets and fixture overrides. |
| `configs/data/alpaca_sip_bars.yaml` | User-configurable Alpaca SIP historical bar download settings. |
| `configs/paper_alpaca.yaml` | Alpaca paper runtime template using external market events. |
| `configs/paper_ibkr.yaml` | IBKR paper runtime template using external market events and `symbol_conids`. |
| `configs/paper_fake_stream.yaml` | Deterministic paper runtime template using finite in-memory market events. |
| `configs/paper_alpaca_stream_mock.yaml` | Deterministic paper runtime template using Alpaca-shaped mock stream payloads. |
| `configs/live_alpaca.yaml` | Guarded live template with dry-run support plus manual submission, Alpaca live adapter construction, and automated preview submission disabled by default. |
| `configs/ml/directional_baseline.yaml` | Offline ML fixture training configuration. |
| `configs/risk/base.yaml` | Reusable risk sizing and rule defaults imported with `risk_ref`. |
| `configs/strategies/sma_crossover.yaml` | Reusable SMA crossover strategy profile imported with `config_ref`. |
| `configs/strategies/rsi_mean_reversion.yaml` | Reusable RSI mean-reversion strategy profile imported with `config_ref`. |
| `configs/strategies/ml_directional.yaml` | Runtime ML strategy profile matching fixture model schema. |

### Scripts

| File | Purpose |
|---|---|
| `scripts/run_backtest.py` | Loads a runtime config, runs `BacktestEngine`, prints fill count and return. |
| `scripts/download_data.py` | Downloads Alpaca SIP historical stock bars to normalized CSV or Parquet partitioned datasets. |
| `scripts/generate_report.py` | Runs a backtest and prints generated report artifact paths, with optional SVG charts. |
| `scripts/run_paper_trading.py` | Initializes configured paper runtime, supports broker mock mode. |
| `scripts/run_live_trading.py` | Initializes guarded live dry-run runtime with explicit safety confirmation. |
| `scripts/train_model.py` | Trains the dependency-free directional ML baseline from an ML config. |

### Package Root

| File | Purpose |
|---|---|
| `src/qts/__init__.py` | Package version export. |
| `src/qts/py.typed` | Marks package as typed for type checkers. |
| `src/qts/cli.py` | Minimal CLI for loading and validating runtime configs. |

### Domain Layer

| File | Purpose |
|---|---|
| `src/qts/domain/enums.py` | Runtime, market data, broker event, order, risk, and adjustment enums; shared open-order status set. |
| `src/qts/domain/models.py` | Dataclass domain models: bars, quotes, signals, intents, orders, fills, broker events, positions, configs, backtest results. |
| `src/qts/domain/__init__.py` | Public exports for domain enums and models. |

Edit this layer only when changing stable public models. Update
`DATA_MODELS.md`, tests, and any adapters that map into changed models.

### Core Layer

| File | Purpose |
|---|---|
| `src/qts/core/config.py` | YAML/env loading, layered config merge, runtime config construction. |
| `src/qts/core/clocks.py` | `RealClock` and `ReplayClock`. |
| `src/qts/core/exceptions.py` | Project exception hierarchy. |
| `src/qts/core/logging_config.py` | Structured JSON-ish logging formatter and setup helper. |
| `src/qts/core/__init__.py` | Public core exports. |

The config loader intentionally supports a small YAML subset when PyYAML is not
installed. Keep config templates simple unless PyYAML becomes a hard dependency.

### Calendar Layer

| File | Purpose |
|---|---|
| `src/qts/calendar/sessions.py` | `MarketSession`, config parsing, built-in US equity calendar, and `MarketSessionService`. |
| `src/qts/calendar/__init__.py` | Public calendar exports. |

The calendar layer is the canonical owner of market-session boundaries. Runtime
modules should call `MarketSessionService` instead of implementing weekday or
local-clock checks directly.

### Market Data Layer

| File | Purpose |
|---|---|
| `src/qts/market_data/interfaces.py` | `MarketDataProvider` and `DataPortal` protocols. |
| `src/qts/market_data/alpaca.py` | Config-driven Alpaca SIP historical stock bar downloader and client. |
| `src/qts/market_data/normalization.py` | CSV reading, bar schema validation, timestamp/symbol normalization, filtering. |
| `src/qts/market_data/providers.py` | CSV provider, optional Parquet provider, partitioned directory loading, replay provider. |
| `src/qts/market_data/portal.py` | Default data portal with replay-bounded reads. |
| `src/qts/market_data/streaming.py` | Alpaca stream adapter boundary, in-memory stream client, and payload normalization. |
| `src/qts/market_data/__init__.py` | Public market data exports. |

Add new data providers here, not in brokers.

### Feature Layer

| File | Purpose |
|---|---|
| `src/qts/features/indicators.py` | Batch indicators: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, VWAP, returns, volatility, volume ratio. |
| `src/qts/features/pipeline.py` | `FeatureSpec`, `FeatureSchema`, `FeaturePipeline`, default feature specs. |
| `src/qts/features/__init__.py` | Public feature exports. |

Feature definitions are shared by rule-based strategies, ML training, and
runtime inference. Avoid hiding feature logic inside strategies.

### Strategy Layer

| File | Purpose |
|---|---|
| `src/qts/strategies/base.py` | Strategy protocol, base class, feature lookup helpers. |
| `src/qts/strategies/rule_based.py` | SMA crossover and RSI mean-reversion strategies plus strategy factory. |
| `src/qts/strategies/ml_strategy.py` | Runtime ML strategy adapter that converts predictions into signals. |
| `src/qts/strategies/__init__.py` | Public strategy exports. |

Strategies produce normalized outputs. They must not import concrete brokers or
submit orders.

### Risk Layer

| File | Purpose |
|---|---|
| `src/qts/risk/types.py` | Rule and sizing result dataclasses. |
| `src/qts/risk/sizing.py` | Position sizing and conversions from signals/targets to trade intents. |
| `src/qts/risk/rules.py` | Symbol restrictions, position notional, gross exposure, buying power, symbol weight, session, daily loss, cooldown rules. |
| `src/qts/risk/engine.py` | `RiskEngine` orchestration and decision construction. |
| `src/qts/risk/__init__.py` | Public risk exports. |

Add new risk controls as rules, then compose them in the engine or factory.

### Execution Layer

| File | Purpose |
|---|---|
| `src/qts/execution/events.py` | Converts normalized broker order/fill/account/position payloads into idempotent broker lifecycle events. |
| `src/qts/execution/orders.py` | Builds `OrderRequest` objects from approved risk decisions and enforces fractional plus quantity/notional exclusivity policy. |
| `src/qts/execution/manager.py` | Tracks normalized order lifecycle, open-order state, and stale-update guards. |
| `src/qts/execution/router.py` | Thin router that delegates to a configured `Brokerage` and builds polling fallback broker events. |
| `src/qts/execution/fills.py` | Simple fill handler hook. |
| `src/qts/execution/engine.py` | Submits approved decisions and processes idempotent broker order/fill events. |
| `src/qts/execution/__init__.py` | Public execution exports. |

Execution should remain broker-agnostic. Vendor-specific fields belong in
broker or integration metadata.

### Broker Layer

| File | Purpose |
|---|---|
| `src/qts/brokers/interfaces.py` | Normalized `Brokerage` protocol. |
| `src/qts/brokers/backtest/brokerage.py` | Simulated broker with order lifecycle, fill policies, cash, positions, slippage, and commission. |
| `src/qts/brokers/backtest/__init__.py` | Backtest broker exports. |
| `src/qts/brokers/alpaca/brokerage.py` | Alpaca paper and explicitly gated live brokerage adapter implementing `Brokerage`. |
| `src/qts/brokers/alpaca/__init__.py` | Alpaca broker exports. |
| `src/qts/brokers/ibkr/brokerage.py` | IBKR paper brokerage adapter implementing `Brokerage`. |
| `src/qts/brokers/ibkr/__init__.py` | IBKR broker exports. |
| `src/qts/brokers/__init__.py` | Top-level broker exports. |

Broker adapters normalize account, order, position, and fill behavior. They may
call `integrations/` clients, but upstream layers should not.

### Integration Layer

| File | Purpose |
|---|---|
| `src/qts/integrations/alpaca/client.py` | Dependency-free Alpaca Trading API REST client boundary. |
| `src/qts/integrations/alpaca/events.py` | Alpaca trade-update broker event adapter boundary and in-memory event client. |
| `src/qts/integrations/alpaca/mapping.py` | Alpaca payload to/from domain model mapping. |
| `src/qts/integrations/alpaca/mock.py` | In-memory Alpaca-like client for tests and mock paper mode. |
| `src/qts/integrations/alpaca/__init__.py` | Alpaca integration exports. |
| `src/qts/integrations/ibkr/client.py` | Dependency-free IBKR Web API client boundary. |
| `src/qts/integrations/ibkr/events.py` | IBKR order-update broker event adapter boundary and in-memory event client. |
| `src/qts/integrations/ibkr/mapping.py` | IBKR payload to/from domain model mapping and reply-prompt detection. |
| `src/qts/integrations/ibkr/mock.py` | In-memory IBKR-like client for tests and mock paper mode. |
| `src/qts/integrations/ibkr/__init__.py` | IBKR integration exports. |
| `src/qts/integrations/futu/__init__.py` | Placeholder for future Futu integration. |
| `src/qts/integrations/polygon/__init__.py` | Placeholder for future Polygon integration. |
| `src/qts/integrations/__init__.py` | Namespace package exports. |

Integration files should know vendor field names. Domain, strategy, risk,
execution, and portfolio files should not.

### Portfolio Layer

| File | Purpose |
|---|---|
| `src/qts/portfolio/accounting.py` | `DefaultPortfolio`, fill application, positions, cash ledger, trade ledger, mark-to-market, reconciliation. |
| `src/qts/portfolio/__init__.py` | Portfolio exports. |

Portfolio state is internal accounting. It is reconciled against broker state
but should not be confused with broker-owned account state.

### Engine Layer

| File | Purpose |
|---|---|
| `src/qts/engines/event_loop.py` | Runtime market-event source protocol, fake stream, validation loop, reconnect/heartbeat policy, and loop result counters. |
| `src/qts/engines/features.py` | Resolves feature specs/schema from strategy configs. |
| `src/qts/engines/market_data.py` | Validates event-driven market data provider settings for paper/live. |
| `src/qts/engines/backtest_engine.py` | Deterministic local backtest orchestration. |
| `src/qts/engines/paper_trading_engine.py` | Paper runtime initialization, externally supplied event handling, and finite fake-stream execution. |
| `src/qts/engines/live_engine.py` | Guarded live orchestration, manual live order submission envelope, selected Alpaca live brokerage construction, automated preview submission, and `_DryRunLiveBrokerage`. |
| `src/qts/engines/__init__.py` | Engine exports. |

Engines wire modules together. Keep detailed business behavior in the owning
layer.

### Reporting Layer

| File | Purpose |
|---|---|
| `src/qts/reporting/charts.py` | Dependency-free SVG equity and drawdown chart diagnostics. |
| `src/qts/reporting/metrics.py` | Return, volatility, Sharpe, drawdown, trade, and exposure metrics. |
| `src/qts/reporting/reporter.py` | Writes Markdown, JSON, CSV, and optional SVG report artifacts. |
| `src/qts/reporting/__init__.py` | Reporting exports. |

Reporting consumes results. It should not change runtime state.

### ML Layer

| File | Purpose |
|---|---|
| `src/qts/ml/types.py` | ML workflow errors, labels, samples, dataset split models, model manifests, approval metadata, and schema hashes. |
| `src/qts/ml/labels.py` | Forward-return label generation. |
| `src/qts/ml/dataset.py` | Builds ML samples from bars, features, and labels. |
| `src/qts/ml/splits.py` | Chronological and walk-forward splitting. |
| `src/qts/ml/leakage.py` | Temporal leakage validation helpers. |
| `src/qts/ml/models.py` | Dependency-free directional model training and evaluation. |
| `src/qts/ml/diagnostics.py` | Serializable manifest diagnostics and strategy diagnostic collection helpers. |
| `src/qts/ml/registry.py` | Filesystem model registry with `model.json`, `manifest.json`, stage transitions, and approval helpers. |
| `src/qts/ml/inference.py` | Runtime model loading, manifest validation, stage policy checks, prediction interface, and prediction metadata enrichment. |
| `src/qts/ml/training.py` | End-to-end directional training pipeline. |
| `src/qts/ml/__init__.py` | ML exports. |

ML training is offline. Runtime trading integration happens through
`strategies/ml_strategy.py`. Newly saved model registry entries include a
portable manifest and feature-schema hash. Runtime configs can require
approved manifests or restrict loading to specific model stages. Predictions,
ML signals, backtest reports, and runtime health payloads carry compact
manifest diagnostics for auditability.

### Monitoring Layer

| File | Purpose |
|---|---|
| `src/qts/monitoring/types.py` | Health status, alert severity, health result, metric, alert, recovery models. |
| `src/qts/monitoring/health.py` | Callable health checks, broker connection health, health monitor aggregation. |
| `src/qts/monitoring/metrics.py` | In-memory runtime metric logger. |
| `src/qts/monitoring/alerts.py` | Alert sinks and alert manager. |
| `src/qts/monitoring/safety.py` | Live safety policy, manual and automated submission gates, and account/order request safety validation. |
| `src/qts/monitoring/reconciliation.py` | Broker/internal reconciliation health check. |
| `src/qts/monitoring/recovery.py` | Recovery manager for stop/retry/escalation behavior. |
| `src/qts/monitoring/__init__.py` | Monitoring exports. |

Monitoring is where live safety checks belong. Do not scatter live safety
policy inside strategies.

### Research and Utils

| File | Purpose |
|---|---|
| `src/qts/research/__init__.py` | Placeholder for future research workflows. |
| `src/qts/utils/__init__.py` | Placeholder for small future cross-cutting helpers. |

Keep these empty until there is a clear owner for new behavior.

### Tests and Fixtures

| File or Directory | Purpose |
|---|---|
| `tests/test_scaffold.py` | Smoke tests for docs, imports, configs, package metadata. |
| `tests/fixtures/market_data/bars.csv` | Small valid OHLCV fixture. |
| `tests/fixtures/market_data/bars_duplicate.csv` | Duplicate timestamp fixture for validation tests. |
| `tests/fixtures/market_data/bars_missing_column.csv` | Missing-column fixture for validation tests. |
| `tests/fixtures/market_data/backtest_sma_cross.csv` | Fixture for deterministic backtest. |
| `tests/fixtures/market_data/ml_directional.csv` | Fixture for ML workflow tests. |
| `tests/unit/domain/` | Domain model and enum tests. |
| `tests/unit/core/` | Config, clocks, and logging tests. |
| `tests/unit/market_data/` | CSV provider, data portal, downloader, and streaming adapter tests. |
| `tests/unit/features/` | Indicator and feature pipeline tests. |
| `tests/unit/strategies/` | Rule-based and ML strategy tests. |
| `tests/unit/risk/` | Sizing and risk engine tests. |
| `tests/unit/execution/` | Order building, routing, and execution tests. |
| `tests/unit/brokers/backtest/` | Backtest broker lifecycle and fill tests. |
| `tests/unit/brokers/alpaca/` | Alpaca brokerage tests with fake clients. |
| `tests/unit/brokers/ibkr/` | IBKR brokerage tests with in-memory client. |
| `tests/unit/integrations/alpaca/` | Alpaca mapping tests. |
| `tests/unit/integrations/ibkr/` | IBKR mapping tests. |
| `tests/unit/portfolio/` | Accounting and reconciliation tests. |
| `tests/unit/reporting/` | Metrics tests. |
| `tests/unit/ml/` | Dataset, registry/inference, split/leakage tests. |
| `tests/unit/monitoring/` | Health, alerts, safety, recovery, reconciliation tests. |
| `tests/integration/backtest/` | End-to-end backtest tests. |
| `tests/integration/alpaca/` | Mocked Alpaca paper engine tests. |
| `tests/integration/ibkr/` | Mocked IBKR paper engine tests. |
| `tests/integration/ml/` | Fixture-backed ML training pipeline test. |
| `tests/integration/live_safety/` | Guarded live dry-run tests. |

Detailed test file index:

| File | Purpose |
|---|---|
| `tests/__init__.py` | Test package marker when present in import paths. |
| `tests/test_scaffold.py` | Verifies required docs, imports, config templates, pyproject metadata, package version. |
| `tests/unit/__init__.py` | Unit test package marker. |
| `tests/unit/domain/__init__.py` | Domain test package marker. |
| `tests/unit/domain/test_enums.py` | Verifies stable enum values. |
| `tests/unit/domain/test_models.py` | Verifies domain validation, normalization, and serialization behavior. |
| `tests/unit/core/__init__.py` | Core test package marker. |
| `tests/unit/core/test_clocks.py` | Tests real and replay clock behavior. |
| `tests/unit/core/test_config.py` | Tests config loading, env parsing, YAML parsing, and invalid config failures. |
| `tests/unit/core/test_logging.py` | Tests structured logging setup. |
| `tests/unit/calendar/test_sessions.py` | Tests market sessions, holidays, early closes, extended hours, and fail-closed behavior. |
| `tests/unit/market_data/__init__.py` | Market data test package marker. |
| `tests/unit/market_data/test_alpaca_downloader.py` | Tests Alpaca SIP timeframe normalization, pagination, CSV/Parquet writing, partitioned datasets, and config loading. |
| `tests/unit/market_data/test_csv_provider.py` | Tests CSV provider, normalization errors, replay ordering, and data portal behavior. |
| `tests/unit/market_data/test_streaming.py` | Tests Alpaca stream payload normalization, filtering, config factory, and fail-closed errors. |
| `tests/unit/features/__init__.py` | Feature test package marker. |
| `tests/unit/features/test_indicators.py` | Known-value tests for indicators. |
| `tests/unit/features/test_pipeline.py` | Tests feature specs, schemas, batch transform, online updates, and empty feature behavior. |
| `tests/unit/strategies/__init__.py` | Strategy test package marker. |
| `tests/unit/strategies/test_rule_based.py` | Tests SMA crossover and RSI signal behavior. |
| `tests/unit/strategies/test_ml_strategy.py` | Tests ML strategy prediction-to-signal conversion and schema validation. |
| `tests/unit/risk/__init__.py` | Risk test package marker. |
| `tests/unit/risk/test_sizing.py` | Tests fixed quantity/notional sizing and signal/target conversion. |
| `tests/unit/risk/test_engine.py` | Tests risk approval, rejection, modification, cooldown, exposure, and buying power behavior. |
| `tests/unit/execution/__init__.py` | Execution test package marker. |
| `tests/unit/execution/test_execution.py` | Tests order request building, fractional validation, routing, order manager, and backtest broker integration. |
| `tests/unit/brokers/__init__.py` | Broker test package marker. |
| `tests/unit/brokers/backtest/__init__.py` | Backtest broker test package marker. |
| `tests/unit/brokers/backtest/test_backtest_brokerage.py` | Tests fill policies, lifecycle, cash/position checks, and rejections. |
| `tests/unit/brokers/alpaca/__init__.py` | Alpaca broker test package marker. |
| `tests/unit/brokers/alpaca/test_alpaca_brokerage.py` | Tests Alpaca brokerage conversion, polling fills, errors, and gated live adapter behavior. |
| `tests/unit/brokers/ibkr/__init__.py` | IBKR broker test package marker. |
| `tests/unit/brokers/ibkr/test_ibkr_brokerage.py` | Tests IBKR brokerage conversion, polling fills, reply prompt rejection, live rejection, and missing `conid` handling. |
| `tests/unit/integrations/__init__.py` | Integration test package marker. |
| `tests/unit/integrations/alpaca/__init__.py` | Alpaca integration test package marker. |
| `tests/unit/integrations/alpaca/test_broker_events.py` | Tests Alpaca trade-update broker event normalization and in-memory event client behavior. |
| `tests/unit/integrations/alpaca/test_mapping.py` | Tests Alpaca order/account/position/fill mapping. |
| `tests/unit/integrations/ibkr/__init__.py` | IBKR integration test package marker. |
| `tests/unit/integrations/ibkr/test_broker_events.py` | Tests IBKR order-update broker event normalization and in-memory event client behavior. |
| `tests/unit/integrations/ibkr/test_mapping.py` | Tests IBKR order/account/position/fill mapping and reply prompt detection. |
| `tests/unit/portfolio/__init__.py` | Portfolio test package marker. |
| `tests/unit/portfolio/test_accounting.py` | Tests fill application, cash ledger, position accounting, and mark-to-market. |
| `tests/unit/portfolio/test_reconciliation.py` | Tests internal portfolio reconciliation against broker account/positions. |
| `tests/unit/reporting/__init__.py` | Reporting test package marker. |
| `tests/unit/reporting/test_metrics.py` | Tests performance metrics and report artifact generation. |
| `tests/unit/ml/__init__.py` | ML test package marker. |
| `tests/unit/ml/test_dataset.py` | Tests ML sample construction from bars, features, and labels. |
| `tests/unit/ml/test_splits_leakage.py` | Tests chronological splits, walk-forward splits, and leakage checks. |
| `tests/unit/ml/test_registry_inference.py` | Tests filesystem model registry and runtime inference. |
| `tests/unit/monitoring/__init__.py` | Monitoring test package marker. |
| `tests/unit/monitoring/helpers.py` | Shared fixtures for monitoring and live safety tests. |
| `tests/unit/monitoring/test_health_alerts_recovery.py` | Tests health checks, alert manager, metrics, and recovery manager. |
| `tests/unit/monitoring/test_reconciliation.py` | Tests broker reconciliation health check. |
| `tests/unit/monitoring/test_safety.py` | Tests live safety config, account allowlist, symbol allowlist, and max order caps. |
| `tests/unit/engines/__init__.py` | Engine test package marker. |
| `tests/unit/engines/test_event_loop.py` | Tests fake stream dispatch, duplicate handling, stale checks, ordering checks, and session filtering. |
| `tests/unit/engines/test_feature_settings.py` | Tests engine feature spec and schema resolution from strategy configs. |
| `tests/unit/engines/test_market_data_settings.py` | Tests paper/live event-driven market data provider validation. |
| `tests/integration/__init__.py` | Integration test package marker. |
| `tests/integration/backtest/__init__.py` | Backtest integration package marker. |
| `tests/integration/backtest/test_backtest_engine.py` | End-to-end backtest tests, including fixture reproducibility. |
| `tests/integration/alpaca/__init__.py` | Alpaca integration package marker. |
| `tests/integration/alpaca/test_paper_trading_engine.py` | Mocked paper engine tests for Alpaca path and shared execution flow. |
| `tests/integration/ibkr/__init__.py` | IBKR integration package marker. |
| `tests/integration/ibkr/test_paper_trading_engine.py` | Mocked paper engine initialization test for IBKR path. |
| `tests/integration/ml/__init__.py` | ML integration package marker. |
| `tests/integration/ml/test_training_pipeline.py` | Fixture-backed end-to-end ML training pipeline test. |
| `tests/integration/live_safety/__init__.py` | Live safety integration package marker. |
| `tests/integration/live_safety/test_live_engine.py` | Guarded live initialization, decision preview, manual submission, Alpaca live adapter construction, and automated submission tests. |

Generated metadata note:

- `src/quant_trading_system_v3.egg-info/` can appear after editable installs.
  Treat it as packaging output, not source code to edit by hand.

## 4. How to Make Common Engineering Changes

### Add a New Rule-Based Strategy

1. Add a class in `src/qts/strategies/rule_based.py` or a new strategy module.
2. Inherit or follow `BaseStrategy`.
3. Emit `Signal`, `TargetPosition`, or `TradeIntent`.
4. Register it in `create_strategy`.
5. Add a config under `configs/strategies/`.
6. Add unit tests under `tests/unit/strategies/`.
7. If feature requirements change, update feature config and tests.

Do not call brokers from the strategy.

### Add a New Indicator

1. Add computation to `src/qts/features/indicators.py`.
2. Add output names, required inputs, and lookback behavior.
3. Add `FeaturePipeline` coverage if needed.
4. Add known-value tests under `tests/unit/features/`.
5. Update strategy or ML configs to use the new feature.

### Add a New Risk Rule

1. Implement a rule class in `src/qts/risk/rules.py`.
2. Return `RuleResult` values consistently.
3. Add the rule to `default_risk_rules` if it should run by default.
4. Add tests under `tests/unit/risk/`.
5. Document config fields in `DATA_MODELS.md` or `INTERFACES.md` if public.

### Add a New Broker Adapter

1. Add low-level vendor client and mapping under `src/qts/integrations/<vendor>/`.
2. Add `src/qts/brokers/<vendor>/brokerage.py` implementing `Brokerage`.
3. Convert all vendor payloads to domain models at the boundary.
4. Add an in-memory mock client for tests.
5. Add config template under `configs/`.
6. Wire selection in the appropriate engine factory.
7. Add unit tests for mapping and brokerage behavior.
8. Add integration tests for mock initialization.
9. Update `DECISIONS.md`, `INTERFACES.md`, `PROJECT_STATE.md`, and `CHANGELOG.md`.

Do not let execution or strategies import vendor clients.

### Add a New Market Data Provider

1. Implement `MarketDataProvider` in `src/qts/market_data/`.
2. Normalize all data into domain `Bar`, `Quote`, or `Trade` models.
3. Keep broker credentials and broker state separate.
4. Add provider selection in engine config factories if needed.
5. Add fixtures and tests under `tests/unit/market_data/`.

### Add a New ML Model Type

1. Add model representation and training logic under `src/qts/ml/`.
2. Keep artifacts serializable through the registry.
3. Preserve feature schema metadata and manifest/schema-hash validation.
4. Add inference support under `src/qts/ml/inference.py` or a parallel adapter.
5. Keep runtime strategy interpretation in `src/qts/strategies/ml_strategy.py` or a new strategy.
6. Add compact diagnostics through `src/qts/ml/diagnostics.py`.
7. Add tests for registry compatibility, schema validation, and diagnostic propagation.

## 5. Debugging Guide

| Problem Area | Start Here | Then Check |
|---|---|---|
| Config loading | `src/qts/core/config.py` | `tests/unit/core/test_config.py`, target YAML |
| Domain validation | `src/qts/domain/models.py` | `DATA_MODELS.md`, `tests/unit/domain/` |
| Bad market data | `src/qts/market_data/normalization.py` | CSV fixture, provider tests |
| Feature mismatch | `src/qts/features/pipeline.py` | strategy `feature_config`, ML model metadata |
| Strategy output wrong | `src/qts/strategies/` | feature rows, strategy tests |
| Risk rejection | `src/qts/risk/rules.py` | risk config, rule results |
| Order not routed | `src/qts/execution/engine.py` | order request builder, router |
| Backtest fill oddity | `src/qts/brokers/backtest/brokerage.py` | fill policy and market events |
| Paper broker issue | `src/qts/brokers/alpaca/` or `src/qts/brokers/ibkr/` | integration mapping tests |
| Portfolio mismatch | `src/qts/portfolio/accounting.py` | reconciliation details |
| Live safety failure | `src/qts/monitoring/safety.py` | `configs/live_alpaca.yaml` |

## 6. Invariants to Preserve

- Domain models remain vendor-neutral.
- Strategies never submit orders.
- Risk owns sizing and approval.
- Execution routes through `Brokerage`.
- Broker adapters convert to/from domain models.
- Market data and brokerage stay separate even for the same vendor.
- Backtest, paper, and live modes share the strategy/risk/execution path.
- Alpaca live adapter construction is gated by the D1 confirmation/submission
  checks.
- Automated live submission is separately gated and fail-stops on submission or
  post-submit reconciliation errors.
- Documentation changes accompany interface, model, or architecture changes.

## 7. Recommended Reading Order

If you are learning the system:

1. `README.md`
2. `docs/user_manual.md`
3. `SYSTEM_DESIGN.md`
4. `INTERFACES.md`
5. `DATA_MODELS.md`
6. `PROJECT_STATE.md`
7. `src/qts/domain/models.py`
8. `src/qts/engines/backtest_engine.py`
9. `src/qts/brokers/backtest/brokerage.py`
10. `tests/integration/backtest/test_backtest_engine.py`

If you are adding broker functionality:

1. `DECISIONS.md` ADR-006, ADR-018, ADR-020, ADR-021
2. `src/qts/brokers/interfaces.py`
3. `src/qts/brokers/alpaca/brokerage.py`
4. `src/qts/brokers/ibkr/brokerage.py`
5. `src/qts/integrations/alpaca/mapping.py`
6. `src/qts/integrations/ibkr/mapping.py`
7. Matching unit tests.

If you are adding strategy or ML functionality:

1. `src/qts/features/pipeline.py`
2. `src/qts/strategies/base.py`
3. `src/qts/strategies/rule_based.py`
4. `src/qts/ml/training.py`
5. `src/qts/strategies/ml_strategy.py`
6. Matching strategy and ML tests.
