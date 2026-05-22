# CHANGELOG.md

# Changelog

This changelog tracks project changes by phase.

The format follows a simplified Keep a Changelog style.

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
