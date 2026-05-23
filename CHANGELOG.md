# CHANGELOG.md

# Changelog

This changelog tracks project changes by phase.

The format follows a simplified Keep a Changelog style.

---

## [Phase 10] - 2026-05-22

### Added

- Added a config-driven Alpaca SIP historical stock bar downloader under
  `qts.market_data.alpaca`.
- Added `scripts/download_data.py` for downloading historical K-line bars to
  normalized CSV or Parquet.
- Added `configs/data/alpaca_sip_bars.yaml` for user-managed download settings.
- Added support for user levels `1min`, `5min`, `15min`, `1hour`, and `1day`.
- Added unit tests for timeframe normalization, paginated responses, CSV/Parquet
  output, and config/env loading.

### Changed

- Exported Alpaca downloader helpers from `qts.market_data`.
- Added config and CLI support for `output.format: csv` or `parquet`.
- Added partitioned dataset output for Alpaca SIP downloads with configurable
  `output.partition_by` fields.
- Updated CSV and Parquet local providers to read partitioned dataset
  directories recursively.
- Replaced the sample fixed data-download filename with partitioned
  `timeframe`/`symbol`/`date` storage so multi-symbol downloads do not land in a
  single large file.
- Updated `.env.example`, README, user manual, system handbook, project state,
  system design, phase plan, and decisions docs for the new data download path.

### Fixed

- None.

### Removed

- None.

---

## [Documentation Additions] - 2026-05-22

### Added

- Added `docs/user_manual.md` with detailed setup, configuration, execution,
  broker, ML, live dry-run, safety, and troubleshooting guidance.
- Added `docs/system_handbook.md` with architecture explanations, runtime
  flows, file-by-file system reference, extension workflows, and debugging maps.

### Changed

- Linked the new manuals from `README.md`.
- Updated `PROJECT_STATE.md` to list the new maintained documentation files.

### Fixed

- None.

### Removed

- None.

---

## [Phase 9] - 2026-05-22

### Added

- Implemented a dependency-free IBKR Web API client boundary under
  `integrations/ibkr/`.
- Added IBKR payload mapping for order requests, normalized orders, fill deltas,
  account summaries, and positions.
- Implemented `IBKRBrokerage` for paper trading through the normalized
  `Brokerage` interface.
- Added an in-memory IBKR client for credential-free mock paper runs.
- Added `configs/paper_ibkr.yaml` with IBKR account and symbol `conid` mapping
  settings.
- Added mocked IBKR tests for mapping, brokerage behavior, fail-closed reply
  prompts, live-mode rejection, and paper engine initialization.

### Changed

- Updated `PaperTradingEngine` to select either `alpaca_paper` or `ibkr_paper`
  from configuration.
- Updated `scripts/run_paper_trading.py` wording so the runner is broker-neutral.
- Updated README, system design, interface, data model, project state, phase
  plan, and environment-example documentation for IBKR paper support.
- Added ADR-021 documenting the IBKR adapter boundary and manual-reply safety
  policy.

### Fixed

- None.

### Removed

- None.

### Notes

- IBKR live order submission remains disabled.
- IBKR order responses that require manual reply confirmation fail closed; the
  adapter does not auto-confirm those prompts.

---

## [Post-Phase 8 Design Review Fixes] - 2026-05-22

### Changed

- Moved the shared open-order status set into the domain layer so
  `BacktestBrokerage` no longer depends on the execution package.
- Added shared engine feature-pipeline settings resolution from
  `StrategyConfig.feature_config`.
- Added explicit event-driven market-data provider validation for paper and live
  engines.
- Added explicit paper broker selection validation from `broker.broker_type`.
- Wired `execution.allow_fractional` into execution order validation and live
  order safety validation.
- Updated the ML strategy fixture config with explicit feature specs and schema
  version for runtime training-serving consistency.
- Updated paper/live configuration templates to declare `external_events` as the
  current supported market-data provider.

### Fixed

- Backtest `DefaultDataPortal` instances now enforce replay bounds so strategies
  cannot read future bars from the injected data portal during replay.
- `FeaturePipeline([])` now preserves an explicit empty feature set instead of
  falling back to default features.
- `MLSignalStrategy` now validates the runtime feature pipeline schema against
  the loaded model during initialization when a pipeline is available.
- Paper/live configs no longer imply that Alpaca market data is implemented in
  the current phase.

### Removed

- None.

---

## [Phase 8] - 2026-05-22

### Added

- Implemented monitoring primitives under `qts.monitoring`:
  - health check results and aggregation,
  - runtime metric logging,
  - alert events and alert sinks,
  - recovery manager behavior,
  - broker/internal reconciliation health checks,
  - live safety validation helpers.
- Added guarded `LiveEngine` scaffolding with explicit safety gates and
  dry-run-only broker initialization.
- Added live order safety validation for allowed symbols, account allowlists,
  max order notional, and max order quantity.
- Added `scripts/run_live_trading.py` for safe dry-run live initialization.
- Added `docs/runbooks.md` with Phase 8 operational procedures.
- Added Phase 8 tests for:
  - live safety gates,
  - account and symbol allowlists,
  - max order size checks,
  - health check aggregation,
  - alert hooks,
  - runtime metrics logging,
  - recovery manager stop behavior,
  - reconciliation mismatches,
  - dry-run live engine initialization.

### Changed

- Updated `configs/live_alpaca.yaml` with explicit live safety defaults.
- Updated `README.md` with Phase 8 status and dry-run live initialization
  instructions.
- Updated `PROJECT_STATE.md` to mark Phase 8 complete.
- Updated `INTERFACES.md` with monitoring and live-safety helper contracts.
- Added ADR-020 documenting the guarded dry-run live-engine foundation.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 8 does not enable real live broker order submission.
- The dry-run live engine validates operational wiring and safety controls
  without touching external broker APIs.

---

## [Phase 7] - 2026-05-22

### Added

- Implemented offline ML dataset construction from existing feature pipelines.
- Added forward-return directional labels with configurable horizon and
  thresholds.
- Added chronological train/validation/test splits, walk-forward split helpers,
  and temporal leakage checks.
- Implemented a dependency-free directional baseline model with training,
  evaluation, and runtime prediction support.
- Added a filesystem model registry under `artifacts/models/` conventions.
- Implemented `DefaultMLModelInference` for loading registered model artifacts
  and producing normalized `ModelPrediction` objects.
- Added `MLSignalStrategy` to convert model predictions into broker-agnostic
  `Signal` outputs.
- Added fixture ML configs:
  - `configs/ml/directional_baseline.yaml`,
  - `configs/strategies/ml_directional.yaml`.
- Added `scripts/train_model.py` for local Phase 7 model training.
- Added Phase 7 tests for:
  - dataset construction and labels,
  - chronological and walk-forward splits,
  - temporal leakage detection,
  - model registry and inference,
  - ML strategy signal conversion,
  - fixture-backed training pipeline execution.

### Changed

- Updated `README.md` with Phase 7 status and local training instructions.
- Updated `PROJECT_STATE.md` to mark Phase 7 complete and Phase 8 pending.
- Added ADR-019 documenting the dependency-free Phase 7 baseline model and local
  registry approach.
- Extended the strategy factory to instantiate the ML signal strategy from
  configuration.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 7 does not introduce advanced model libraries, online learning,
  optimization, production model monitoring, or live trading readiness.
- The initial ML model is intentionally small and dependency-free so workflow
  contracts can be tested in the current local environment.

---

## [Phase 6] - 2026-05-22

### Added

- Implemented a dependency-free Alpaca Trading API client boundary under
  `integrations/alpaca/`.
- Added Alpaca payload mapping for:
  - order requests,
  - normalized orders,
  - fill deltas from polled order state,
  - accounts,
  - positions.
- Implemented `AlpacaBrokerage` for paper trading through the normalized
  `Brokerage` interface.
- Added an in-memory Alpaca client for credential-free mock paper runs.
- Implemented portfolio reconciliation against broker account and positions.
- Implemented `PaperTradingEngine` initialization and externally supplied
  market-event handling for paper mode.
- Added `scripts/run_paper_trading.py` for paper runtime initialization.
- Added mocked Phase 6 tests for:
  - Alpaca mapping,
  - broker order submission and fill polling,
  - broker error normalization,
  - live-mode safety rejection,
  - portfolio reconciliation,
  - mock paper engine initialization,
  - shared paper execution path from strategy to portfolio fill.

### Changed

- Updated `configs/paper_alpaca.yaml` with explicit paper safety settings.
- Updated `README.md` with Phase 6 status and mock paper runtime instructions.
- Updated `PROJECT_STATE.md` to mark Phase 6 complete and Phase 7 pending.
- Added ADR-018 documenting the Alpaca REST boundary, mock client, and polling
  fill approach.
- Updated `.env.example` to describe Alpaca credentials as active paper
  configuration values.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 6 does not enable live trading.
- Alpaca market data and streaming order updates remain separate future work.
- Paper fills are currently detected by polling order filled-quantity deltas.

---

## [Phase 5] - 2026-05-22

### Added

- Implemented internal portfolio accounting with:
  - fill application,
  - position accounting,
  - realized and unrealized PnL,
  - cash ledger entries,
  - trade ledger entries,
  - mark-to-market portfolio snapshots.
- Implemented reporting metrics:
  - total return,
  - annualized return when the period is long enough,
  - volatility,
  - Sharpe ratio,
  - max drawdown,
  - win rate,
  - profit factor,
  - average trade PnL,
  - trade counts,
  - exposure summary.
- Implemented `BacktestReporter` for Markdown, JSON, and CSV artifact export.
- Implemented deterministic bar-driven `BacktestEngine` wiring together market
  data, features, strategy, risk, execution, backtest brokerage, portfolio, and
  reporting.
- Added runnable scripts:
  - `scripts/run_backtest.py`,
  - `scripts/generate_report.py`.
- Added a local SMA crossover fixture config and CSV fixture:
  - `configs/backtest_fixture.yaml`,
  - `tests/fixtures/market_data/backtest_sma_cross.csv`.
- Added Phase 5 tests for:
  - portfolio accounting,
  - metric calculation,
  - report artifact export,
  - end-to-end backtest execution,
  - empty-signal backtests,
  - fixed-fixture reproducibility.

### Changed

- Updated `README.md` to reflect Phase 5 status and fixture backtest commands.
- Updated `PROJECT_STATE.md` to mark Phase 5 complete and Phase 6 pending.
- Added ADR-017 documenting the deterministic bar-driven Phase 5 backtest engine
  and artifact-export approach.
- Added strategy attribution to backtest broker order metadata so portfolio trade
  ledgers can preserve strategy IDs without changing stable fill models.

### Fixed

- Avoided intraday annualized-return overflow by returning no annualized value
  for periods shorter than one day.

### Removed

- None.

### Notes

- Phase 5 does not implement Alpaca integration, paper/live runtime engines, ML
  workflows, operational monitoring, or visual plotting.
- Report output is intentionally lightweight and dependency-free: Markdown,
  JSON, and CSV.

---

## [Phase 4] - 2026-05-22

### Added

- Implemented normalized `Brokerage` protocol.
- Implemented execution workflow components:
  - `build_order_request`,
  - `OrderManager`,
  - `OrderRouter`,
  - `FillHandler`,
  - `ExecutionEngine`.
- Implemented `BacktestBrokerage` with broker-side order, fill, cash, account,
  and position state.
- Added simulated order lifecycle behavior for accepted, rejected, submitted,
  partially filled, filled, canceled, and expired orders.
- Added simulated market, limit, stop, and stop-limit order handling.
- Added deterministic fill policies:
  - `next_bar_open`,
  - `next_bar_close`,
  - `next_bar_typical_price`,
  - `quote_bid_ask`.
- Added simple commission and slippage models for backtest fills.
- Added broker-side buying-power/cash and position checks.
- Added Phase 4 unit tests for:
  - order request construction,
  - rejected risk decision handling,
  - order routing,
  - order manager cancellation and open-order tracking,
  - market, limit, stop, quote, partial-fill, insufficient-cash, cancellation,
    slippage, and commission behavior.

### Changed

- Updated `README.md` to reflect Phase 4 status and execution/backtest broker
  modules.
- Updated `PROJECT_STATE.md` to mark Phase 4 complete and Phase 5 pending.
- Added ADR-016 documenting the Phase 4 backtest brokerage state and fill-policy
  decisions.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 4 does not implement a full backtest engine, internal portfolio
  accounting, ledgers, reporting, Alpaca integration, ML workflows, or live/paper
  trading runtime behavior.
- `BacktestBrokerage` does not load historical data; callers must provide market
  events from the market data layer or future engines.

---

## [Phase 3] - 2026-05-22

### Added

- Implemented broker-agnostic strategy contracts and shared strategy helpers.
- Implemented example rule-based strategies:
  - `SMACrossoverStrategy`,
  - `RSIMeanReversionStrategy`,
  - `create_strategy` factory for Phase 3 strategy configs.
- Implemented signal and target-position conversion into normalized
  `TradeIntent` objects.
- Implemented `DefaultPositionSizer` with fixed quantity, fixed notional, and
  percent-of-equity sizing policies.
- Implemented risk result helpers, default risk rules, and `RiskEngine`.
- Added basic risk rules for:
  - symbol allow/block lists,
  - trading session checks,
  - daily loss limit placeholder,
  - cooldown,
  - max position notional,
  - max symbol weight,
  - max gross exposure,
  - buying power.
- Added Phase 3 configuration templates under `configs/strategies/` and
  `configs/risk/`.
- Added Phase 3 unit tests for deterministic strategy output, signal/target
  conversion, sizing, approvals, rejections, risk modifications, session checks,
  buying power, daily-loss rejection, gross exposure, and cooldown.

### Changed

- Updated `README.md` to reflect Phase 3 status and the new strategy/risk
  modules.
- Updated `PROJECT_STATE.md` to mark Phase 3 complete and Phase 4 pending.
- Added ADR-015 documenting the Phase 3 signal-first strategy behavior and
  risk-owned sizing decision.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 3 does not implement order routing, broker adapters, fill simulation,
  portfolio accounting, backtest orchestration, reporting, ML workflows, or
  live/paper trading runtime behavior.
- Strategy and risk tests run with standard-library `unittest`.

---

## [Phase 2] - 2026-05-22

### Added

- Implemented market data protocols for `MarketDataProvider` and `DataPortal`.
- Implemented historical bar normalization helpers:
  - required bar column validation,
  - UTC timestamp normalization,
  - symbol normalization,
  - duplicate symbol/timestamp/timeframe detection,
  - date/symbol/timeframe filtering.
- Implemented local market data providers:
  - `CSVBarProvider`,
  - `LocalParquetProvider` using optional pandas or pyarrow,
  - `ReplayMarketDataProvider`.
- Implemented `DefaultDataPortal` for historical bar access, current market event
  state, quote passthrough, and feature-frame access.
- Implemented reusable batch indicators:
  - SMA,
  - EMA,
  - RSI,
  - MACD,
  - Bollinger Bands,
  - ATR,
  - VWAP,
  - returns,
  - volatility,
  - volume mean,
  - volume ratio.
- Implemented `FeatureSpec`, `FeatureSchema`, and `FeaturePipeline`.
- Added CSV market data fixtures for normal, duplicate, and missing-column cases.
- Added Phase 2 unit tests for:
  - CSV loading and normalization,
  - missing-column errors,
  - duplicate timestamp errors,
  - deterministic replay order,
  - data portal access,
  - known-value indicators,
  - feature pipeline output and schema validation.

### Changed

- Updated `README.md` to reflect Phase 2 status, optional Parquet dependencies,
  and CSV provider usage.
- Added optional `data` dependency extra for pandas/pyarrow-backed Parquet loading.
- Updated `PROJECT_STATE.md` to mark Phase 2 complete and Phase 3 pending.
- Added ADR-014 documenting row-oriented feature frames and optional Parquet
  dependencies.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 2 does not implement strategies, risk rules, execution logic, brokers,
  portfolio accounting, engines, reporting, ML workflows, or live/paper trading
  runtime behavior.
- CSV fixtures and tests run without third-party dependencies. Parquet loading
  requires installing optional `data` dependencies.

---

## [Phase 1] - 2026-05-22

### Added

- Implemented stable domain enums from `DATA_MODELS.md`.
- Implemented validated dataclass domain models for:
  - market data objects,
  - signals and trade intents,
  - risk decisions,
  - orders and fills,
  - positions, accounts, and portfolio snapshots,
  - ledger entries,
  - backtest results,
  - feature and prediction records,
  - strategy, risk, broker, and runtime config models.
- Added domain serialization helpers that normalize enums and UTC timestamps.
- Implemented core configuration loading and validation:
  - layered YAML config loading with `extends`,
  - deep merge behavior,
  - `.env` key-value loading,
  - validated `RuntimeConfig` construction,
  - optional PyYAML support with a small internal parser for repository templates.
- Implemented `RealClock` and `ReplayClock`.
- Implemented common exception categories.
- Implemented basic logging setup with plain text or JSON formatting.
- Added CLI config validation with `qts --config configs/backtest.yaml`.
- Added Phase 1 unit tests for domain validation, enum values, config loading,
  clocks, and logging.

### Changed

- Updated config templates with valid default symbols, date range, and strategy
  config shape so Phase 1 config loading can validate them.
- Updated `README.md` with Phase 1 status, test commands, and config validation
  instructions.
- Updated `PROJECT_STATE.md` to mark Phase 1 complete and Phase 2 pending.
- Added ADR-013 documenting the standard-library dataclass/config-parser choice.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 1 does not implement market data providers, indicators, strategies,
  risk rules, execution logic, brokers, portfolio accounting, engines, reporting,
  ML, or live/paper trading runtime behavior.
- Tests run locally with `unittest`; `pytest` remains an optional dependency and
  was not installed in the current virtual environment.

---

## [Phase 0] - 2026-05-22

### Added

- Created initial documentation package:
  - `SYSTEM_DESIGN.md`
  - `PHASE_PLAN.md`
  - `INTERFACES.md`
  - `DATA_MODELS.md`
  - `DECISIONS.md`
  - `PROJECT_STATE.md`
  - `CHANGELOG.md`
- Defined modular quantitative trading system architecture.
- Defined phase-by-phase implementation plan.
- Defined core interfaces for:
  - market data,
  - features,
  - strategies,
  - ML inference,
  - risk,
  - execution,
  - brokerage,
  - portfolio,
  - engines,
  - reporting.
- Defined stable domain data models.
- Recorded initial architectural decisions.
- Initialized project state and next implementation task.
- Initialized Git repository metadata.
- Added repository scaffold:
  - `pyproject.toml`
  - `README.md`
  - `.env.example`
  - `.gitignore`
  - `configs/base.yaml`
  - `configs/backtest.yaml`
  - `configs/paper_alpaca.yaml`
  - `configs/live_alpaca.yaml`
  - `src/qts/` package layout
  - `tests/test_scaffold.py`
  - `data/.gitkeep`
  - `artifacts/.gitkeep`
- Added placeholder package modules matching the architecture in `SYSTEM_DESIGN.md`.
- Added standard-library smoke tests for required docs, package imports,
  configuration templates, and project metadata.

### Changed

- Updated `PROJECT_STATE.md` to reflect that repository scaffolding exists while
  Phase 1 domain/core implementation remains pending.

### Fixed

- None.

### Removed

- None.

### Notes

- No trading business logic has been implemented.
- No domain models, config loader, clocks, broker adapters, strategies, risk
  rules, execution logic, portfolio accounting, engines, or reporting logic have
  been implemented.
- Phase 1 should start with domain models, core config loading, clocks,
  exceptions, logging, and focused tests.
