# PHASE_PLAN.md

# Phase-by-Phase Implementation Plan

## 1. General Implementation Rules

Every implementation session must:

1. Read `PROJECT_STATE.md`, `PHASE_PLAN.md`, `DECISIONS.md`, `INTERFACES.md`, `DATA_MODELS.md`, and `CHANGELOG.md`.
2. Inspect the current repository state.
3. Identify the current phase and next unfinished task.
4. Implement only the current phase unless minimal future-phase scaffolding is required for testability.
5. Write tests for implemented functionality.
6. Update `PROJECT_STATE.md` and `CHANGELOG.md`.
7. Update `DECISIONS.md`, `INTERFACES.md`, or `DATA_MODELS.md` if public design changes are made.

The project should be implemented by functional milestones, not by individual files.

---

## Phase 0: Documentation and Project Skeleton Planning

### Objective

Create the documentation package that defines system design, phase plan, interfaces, data models, decisions, initial project state, and changelog.

### Scope

- Create:
  - `SYSTEM_DESIGN.md`
  - `PHASE_PLAN.md`
  - `INTERFACES.md`
  - `DATA_MODELS.md`
  - `DECISIONS.md`
  - `PROJECT_STATE.md`
  - `CHANGELOG.md`
- No application code.
- No package initialization yet.

### Out of Scope

- Source code.
- Tests.
- Real data loading.
- Broker integration.

### Expected Files or Modules

Documentation files only.

### Functional Requirements

- Documents must be internally consistent.
- Documents must define module boundaries, interfaces, and phase plan.
- Documents must be suitable for an AI coding agent.

### Testing Requirements

- Manual consistency review.

### Acceptance Criteria

- All seven required Markdown documents exist.
- `PROJECT_STATE.md` points to Phase 1 as the next implementation phase.
- Interfaces and data models are aligned.
- Decisions are reflected in system design.

### Expected Deliverables

- Seven Markdown files.
- Optional compressed archive containing all documentation files.

### Notes for Coding Agent

Phase 0 is complete when this documentation package exists. The next coding task is Phase 1.

### Required Updates

- Initialize `PROJECT_STATE.md`.
- Initialize `CHANGELOG.md`.

---

## Phase 1: Project Skeleton and Core Domain Models

### Objective

Initialize the Python project structure and implement stable domain models, enums, core config loading, clocks, exceptions, and basic logging.

### Scope

- Create Python package using `src/qts/`.
- Add `pyproject.toml`.
- Add `.env.example`, `.gitignore`, and README skeleton.
- Implement domain models and enums from `DATA_MODELS.md`.
- Implement config loading and validation.
- Implement `RealClock` and `ReplayClock`.
- Implement common exceptions and logging setup.

### Out of Scope

- Market data loading.
- Indicators.
- Strategies.
- Broker adapters.
- Backtest engine.
- ML training.

### Expected Files or Modules

- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `src/qts/domain/`
- `src/qts/core/`
- `src/qts/cli.py`
- `configs/base.yaml`
- `configs/backtest.yaml`
- `configs/paper_alpaca.yaml`
- `configs/live_alpaca.yaml`
- `tests/unit/domain/`
- `tests/unit/core/`

### Functional Requirements

- Domain models validate required fields.
- Timestamps are timezone-aware.
- Symbols are normalized to uppercase.
- Enum values are explicit and stable.
- Config loader merges base and mode-specific configuration.
- Secrets are read only from environment variables or `.env`.
- Clocks expose a common interface:
  - current timestamp,
  - advance behavior for replay clock,
  - real current time for real clock.

### Testing Requirements

- Unit tests for model validation.
- Unit tests for enum values.
- Unit tests for config loading.
- Unit tests for clock behavior.
- Unit tests for invalid config failure.

### Acceptance Criteria

- `pytest` can run successfully.
- Package imports work from `src/qts`.
- Basic config can be loaded for backtest mode.
- Domain objects can be constructed and serialized.

### Expected Deliverables

- Runnable project skeleton.
- Stable domain model layer.
- Core infrastructure foundation.

### Notes for Coding Agent

Do not add strategy, broker, or data-provider logic in this phase. Only create placeholder modules if necessary for package structure.

### Required Updates

- Mark Phase 1 complete in `PROJECT_STATE.md`.
- Add Phase 1 entry to `CHANGELOG.md`.
- Update `DATA_MODELS.md` if model fields change.
- Update `DECISIONS.md` for new architectural assumptions.

---

## Phase 2: Market Data and Feature Layer

### Objective

Implement local historical data loading, normalized data access, reusable indicators, and feature pipelines.

### Scope

- Implement `MarketDataProvider` and `DataPortal` interfaces.
- Implement local Parquet provider.
- Implement CSV fixture provider for tests and debugging.
- Implement historical data normalization.
- Implement batch indicators:
  - SMA,
  - EMA,
  - RSI,
  - MACD,
  - Bollinger Bands,
  - ATR,
  - VWAP,
  - returns,
  - volatility,
  - volume features.
- Implement feature schema and feature pipeline.
- Implement basic replay provider for historical bars.

### Out of Scope

- Live market data streaming.
- Alpaca market data integration.
- Strategy implementations beyond simple test stubs.
- Backtest order execution.
- ML training pipeline.

### Expected Files or Modules

- `src/qts/market_data/`
- `src/qts/features/`
- `tests/unit/market_data/`
- `tests/unit/features/`
- `tests/fixtures/market_data/`
- `scripts/download_data.py` as a placeholder or simple local utility if needed.

### Functional Requirements

- Load historical bars from Parquet.
- Load small CSV fixtures.
- Validate required bar columns.
- Normalize timestamps to UTC.
- Enforce stable symbol representation.
- Provide bar sequences for backtests.
- Compute indicators consistently in batch mode.
- Feature pipeline outputs `FeatureFrame` or `FeatureRecord`.

### Testing Requirements

- Known-value tests for indicators.
- Data normalization tests.
- Missing column tests.
- Duplicate timestamp tests.
- Replay ordering tests.
- Feature schema validation tests.

### Acceptance Criteria

- Local historical bar data can be loaded into normalized `Bar` objects or tabular frame.
- Feature pipeline can compute at least SMA, EMA, RSI, returns, and volatility.
- Replay provider can iterate bars in deterministic order.
- Tests pass.

### Expected Deliverables

- Usable local market data layer.
- Reusable feature and indicator layer.
- Test fixtures for future phases.

### Notes for Coding Agent

Indicators must not be implemented inside strategies. The same feature functions should later support both ML dataset construction and strategy inference.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if provider or feature contracts change.
- Update `DATA_MODELS.md` if feature data models change.

---

## Phase 3: Strategy and Risk Layer

### Objective

Implement the base strategy interface, example rule-based strategies, signal/trade intent generation, risk engine, position sizing, and basic risk rules.

### Scope

- Implement base `Strategy` interface.
- Implement SMA crossover strategy.
- Implement RSI mean reversion strategy.
- Implement normalized `Signal`, `TargetPosition`, and `TradeIntent` generation.
- Implement `RiskRule`, `RiskEngine`, and `PositionSizer`.
- Implement basic rules:
  - max position size,
  - max gross exposure,
  - buying power check using portfolio snapshot,
  - symbol allowlist/blocklist,
  - trading session check,
  - daily loss limit placeholder,
  - cooldown rule.
- Implement risk decision result with reasons.

### Out of Scope

- Order routing.
- Broker implementation.
- Fill simulation.
- Full backtest engine.
- ML training.

### Expected Files or Modules

- `src/qts/strategies/`
- `src/qts/risk/`
- `tests/unit/strategies/`
- `tests/unit/risk/`
- `configs/strategies/`
- `configs/risk/`

### Functional Requirements

- Strategies consume market data/features and emit normalized domain objects.
- Strategies remain broker-agnostic.
- Risk engine consumes trade intents and portfolio snapshot.
- Risk engine outputs approved, rejected, or modified decisions.
- Position sizing is performed in risk layer or by risk-approved sizing policy.
- Risk decisions include reason codes.

### Testing Requirements

- Strategy output tests for deterministic sample data.
- Risk approval/rejection tests.
- Position sizing tests.
- Exposure limit tests.
- Symbol restriction tests.
- Cooldown rule tests.

### Acceptance Criteria

- SMA crossover strategy produces expected signals on test data.
- RSI strategy produces expected signals on test data.
- Risk engine can approve, reject, and modify trade intents.
- Tests pass.

### Expected Deliverables

- Broker-agnostic strategy layer.
- Independent risk layer.
- Example strategies ready for backtest integration.

### Notes for Coding Agent

Do not let strategies submit orders. Do not let risk depend on a specific strategy class.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if strategy or risk contracts change.
- Update `DECISIONS.md` for new risk or sizing decisions.

---

## Phase 4: Execution Layer and BacktestBrokerage

### Objective

Implement execution workflow and a simulated backtest brokerage that behaves like a real brokerage adapter.

### Scope

- Implement:
  - `ExecutionEngine`,
  - `OrderManager`,
  - `OrderRouter`,
  - order request builder,
  - fill handler,
  - `Brokerage` interface,
  - `BacktestBrokerage`.
- Implement order lifecycle:
  - accepted,
  - rejected,
  - submitted,
  - partially filled if practical,
  - filled,
  - canceled,
  - expired.
- Implement simulated order types:
  - market,
  - limit,
  - stop if included in scope.
- Implement configurable fill policy:
  - next bar open,
  - next bar close,
  - next bar midpoint/typical price,
  - current quote bid/ask when quote data exists.
- Implement slippage and commission models.
- Implement buying power and cash checks.
- Implement backtest account and position updates.

### Out of Scope

- Full backtest engine reporting.
- Alpaca integration.
- Live order streaming.
- Advanced order book simulation.

### Expected Files or Modules

- `src/qts/execution/`
- `src/qts/brokers/`
- `src/qts/brokers/backtest/`
- `tests/unit/execution/`
- `tests/unit/brokers/backtest/`

### Functional Requirements

- Execution layer converts approved risk decisions to `OrderRequest`.
- Order manager tracks order status.
- Order router submits only to `Brokerage` interface.
- BacktestBrokerage simulates order acceptance/rejection and fills.
- Fill simulation uses market data supplied by the market data layer or engine.
- BacktestBrokerage does not load historical data itself.

### Testing Requirements

- Order request validation tests.
- Market order fill tests.
- Limit order fill tests.
- Rejection tests for insufficient buying power.
- Slippage/commission tests.
- Order lifecycle tests.
- Partial fill tests if implemented.

### Acceptance Criteria

- Approved trade intent can become an order request.
- Order request can be routed to `BacktestBrokerage`.
- BacktestBrokerage can generate fills and update internal broker account state.
- Tests pass.

### Expected Deliverables

- Reusable execution layer.
- First complete brokerage implementation for backtesting.

### Notes for Coding Agent

Keep broker state and internal portfolio state conceptually separate. The backtest broker may maintain simulated account state, but portfolio accounting remains in `portfolio/`.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if execution or brokerage contracts change.
- Update `DATA_MODELS.md` if order or fill models change.
- Update `DECISIONS.md` if fill policy defaults are chosen.

---

## Phase 5: Backtest Engine and Reporting

### Objective

Connect market data, features, strategy, risk, execution, backtest brokerage, portfolio, and reporting into an end-to-end backtest.

### Scope

- Implement `BacktestEngine`.
- Implement portfolio accounting.
- Implement trade ledger and cash ledger.
- Implement mark-to-market snapshots.
- Implement reporting metrics:
  - total return,
  - annualized return if frequency allows,
  - volatility,
  - Sharpe ratio,
  - max drawdown,
  - win rate,
  - profit factor,
  - average trade PnL,
  - number of trades,
  - exposure summary.
- Implement report export to `artifacts/backtests/` and `artifacts/reports/`.
- Implement plotting:
  - equity curve,
  - drawdown,
  - optional price chart with buy/sell markers.

### Out of Scope

- Alpaca paper trading.
- ML training.
- Production monitoring.
- Full dashboard.

### Expected Files or Modules

- `src/qts/engines/backtest_engine.py`
- `src/qts/portfolio/`
- `src/qts/reporting/`
- `scripts/run_backtest.py`
- `scripts/generate_report.py`
- `tests/integration/backtest/`
- `tests/unit/portfolio/`
- `tests/unit/reporting/`

### Functional Requirements

- Backtest engine orchestrates full event or bar loop.
- Portfolio updates from fills.
- Portfolio snapshots are recorded.
- Reports are generated from backtest result.
- Backtest output is reproducible for fixed input data and config.
- Example SMA crossover strategy runs end-to-end.

### Testing Requirements

- Portfolio accounting tests.
- Metric calculation tests.
- End-to-end backtest smoke test.
- Empty signal test.
- Reproducibility test with fixed fixture data.

### Acceptance Criteria

- `scripts/run_backtest.py` can run an SMA crossover strategy on local fixture/historical data.
- Report includes metrics, trade ledger, equity curve, and configuration summary.
- Tests pass.

### Expected Deliverables

- First end-to-end working system.
- Backtest result artifacts.
- Reporting foundation.

### Notes for Coding Agent

This phase is the first major integration milestone. Prefer a simple, deterministic bar-driven engine over a broad incomplete event framework if time is limited.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if engine or reporter contracts change.
- Update `DECISIONS.md` for backtest engine style and default fill policy.

---

## Phase 6: Alpaca Paper Trading Integration

### Objective

Add Alpaca paper trading adapter while reusing strategy, risk, execution, and portfolio logic.

### Scope

- Implement low-level Alpaca integration clients under `integrations/alpaca/`.
- Implement `AlpacaBrokerage` under `brokers/alpaca/`.
- Implement Alpaca paper broker configuration.
- Implement paper trading runner.
- Implement broker fill/order status polling or stream handling.
- Implement portfolio reconciliation with Alpaca account and positions.
- Optionally implement Alpaca market data provider, while keeping it separate from brokerage.

### Out of Scope

- Live trading enablement.
- Complex multi-broker support.
- Full production deployment.

### Expected Files or Modules

- `src/qts/integrations/alpaca/`
- `src/qts/brokers/alpaca/`
- `src/qts/market_data/alpaca/` if implemented
- `src/qts/engines/paper_trading_engine.py`
- `scripts/run_paper_trading.py`
- `tests/integration/alpaca/`
- `tests/unit/brokers/alpaca/`

### Functional Requirements

- Alpaca API details are isolated.
- Alpaca orders are converted from/to internal domain models.
- Paper trading uses the same execution interface as backtesting.
- Portfolio updates from real paper fills.
- Credentials come from environment variables.

### Testing Requirements

- Mocked Alpaca API tests.
- Order conversion tests.
- Broker error handling tests.
- Reconciliation tests.
- Dry-run paper engine smoke test with mocks.

### Acceptance Criteria

- Paper trading runner can initialize without real credentials in mock mode.
- With credentials, system can submit paper orders through Alpaca adapter.
- Strategy, risk, and execution code do not change from backtest mode.
- Tests pass.

### Expected Deliverables

- First real broker adapter.
- Paper trading runtime path.

### Notes for Coding Agent

Do not couple Alpaca market data and Alpaca brokerage even if both use Alpaca SDKs.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if brokerage contracts change.
- Update `DECISIONS.md` for Alpaca-specific assumptions.

---

## Phase 7: ML Workflow

### Objective

Implement offline ML workflow and runtime ML strategy adapter.

### Scope

- Implement dataset builder.
- Implement label builder.
- Implement train/validation/test split.
- Implement walk-forward validation.
- Implement leakage checks.
- Implement model training pipeline.
- Implement model evaluation.
- Implement model registry.
- Implement inference pipeline.
- Implement ML strategy adapter that converts predictions into normalized signals/trade intents.

### Out of Scope

- Advanced feature store.
- Online learning.
- Distributed training.
- Automatic strategy optimization.
- Production model monitoring.

### Expected Files or Modules

- `src/qts/ml/`
- `src/qts/strategies/ml_strategy.py`
- `scripts/train_model.py`
- `configs/ml/`
- `artifacts/models/`
- `tests/unit/ml/`
- `tests/integration/ml/`

### Functional Requirements

- ML training is offline.
- Feature construction reuses `features/`.
- Dataset split avoids look-ahead leakage.
- Model registry records model metadata and feature schema.
- Runtime inference enforces training-serving consistency.
- ML strategy emits the same output types as rule-based strategies.

### Testing Requirements

- Dataset construction tests.
- Label generation tests.
- Split correctness tests.
- Leakage check tests.
- Model registry tests.
- Inference schema compatibility tests.
- ML strategy output tests.

### Acceptance Criteria

- A simple trained model can be saved to the model registry.
- Runtime ML strategy can load model, compute features, predict, and generate normalized trade intents.
- Tests pass.

### Expected Deliverables

- Offline ML training workflow.
- Runtime ML strategy integration.

### Notes for Coding Agent

Do not treat the trained model as a complete strategy. The runtime strategy is responsible for feature preparation, prediction interpretation, and trade intent generation.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `INTERFACES.md` if ML inference contracts change.
- Update `DATA_MODELS.md` if prediction or feature model changes.
- Update `DECISIONS.md` for ML framework assumptions.

---

## Phase 8: Monitoring, Reconciliation, and Live-Trading Readiness

### Objective

Add operational safeguards required before live trading can be considered.

### Scope

- Implement health checks.
- Implement runtime metrics logging.
- Implement alert hooks.
- Implement broker reconciliation checks.
- Implement recovery behavior.
- Implement runbooks.
- Add explicit live-trading safety gates.
- Add guarded `LiveEngine` scaffolding.

### Out of Scope

- Fully automated production deployment.
- Unguarded live trading.
- Complex dashboard.
- Multi-broker routing.

### Expected Files or Modules

- `src/qts/monitoring/`
- `src/qts/engines/live_engine.py`
- `docs/runbooks.md`
- `scripts/run_live_trading.py`
- `tests/unit/monitoring/`
- `tests/integration/live_safety/`

### Functional Requirements

- Live mode cannot run unless explicit safety config is enabled.
- Account, symbol, and max order size guards are enforced.
- Reconciliation detects broker/internal state mismatch.
- Alerts report critical runtime failures.
- Runbooks explain operational procedures.

### Testing Requirements

- Live safety gate tests.
- Reconciliation mismatch tests.
- Alert hook tests.
- Recovery behavior tests.
- Live engine dry-run tests.

### Acceptance Criteria

- Live mode is guarded by explicit configuration.
- Dry-run live engine can initialize safely.
- Reconciliation and monitoring tests pass.
- Runbooks exist.

### Expected Deliverables

- Operational readiness layer.
- Guarded live trading foundation.

### Notes for Coding Agent

Live trading may remain disabled by default. Safety takes priority over feature completeness.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `DECISIONS.md`.
- Update runbooks and interface docs if behavior changes.

---

## Phase 9: IBKR Paper Brokerage Foundation

### Objective

Add an Interactive Brokers paper brokerage adapter while preserving the existing
brokerage interface and keeping live trading fail-closed.

### Scope

- Implement low-level IBKR Web API client boundaries under `integrations/ibkr/`.
- Implement `IBKRBrokerage` under `brokers/ibkr/`.
- Add IBKR paper configuration.
- Reuse the existing paper trading runner and `PaperTradingEngine`.
- Implement mocked IBKR client support for credential-free dry runs.
- Add order, account, position, and fill mapping tests.

### Out of Scope

- IBKR live order submission.
- Automatic confirmation of IBKR reply prompts.
- IBKR market data integration.
- Multi-broker smart routing.

### Expected Files or Modules

- `src/qts/integrations/ibkr/`
- `src/qts/brokers/ibkr/`
- `configs/paper_ibkr.yaml`
- `tests/unit/integrations/ibkr/`
- `tests/unit/brokers/ibkr/`
- `tests/integration/ibkr/`

### Functional Requirements

- IBKR API details are isolated from strategy, risk, execution, and portfolio
  modules.
- IBKR orders are converted from/to internal domain models.
- IBKR paper mode uses the same `Brokerage` interface as backtest and Alpaca.
- Credentials and endpoint overrides come from environment variables.
- IBKR order replies requiring manual confirmation fail closed.

### Testing Requirements

- Mocked IBKR client tests.
- Order conversion tests.
- Broker error and safety tests.
- Mock paper engine initialization test.

### Acceptance Criteria

- `PaperTradingEngine` can initialize with `configs/paper_ibkr.yaml` in mock
  mode without credentials.
- `IBKRBrokerage` can submit normalized paper orders through the mocked client.
- IBKR live configuration is rejected.
- Tests pass.

### Expected Deliverables

- Second paper brokerage adapter.
- IBKR paper runtime initialization path.

### Notes for Coding Agent

Do not couple IBKR market data into brokerage. Do not auto-confirm IBKR order
reply prompts.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `DECISIONS.md`.
- Update `INTERFACES.md` and `DATA_MODELS.md` if contract documentation needs to
  mention IBKR-specific configuration.

---

## Phase 10: Alpaca SIP Historical Data Download

### Objective

Add a user-configurable script for downloading Alpaca SIP historical stock
K-line data into normalized CSV or Parquet partitioned datasets that existing
local providers can read.

### Scope

- Implement a dependency-free Alpaca market data client boundary under
  `market_data/`.
- Implement a config-driven download script.
- Add a download config template.
- Support K-line levels:
  - `1min`,
  - `5min`,
  - `15min`,
  - `1hour`,
  - `1day`.
- Write normalized CSV/Parquet partitioned output compatible with
  `CSVBarProvider` and `LocalParquetProvider`.
- Add tests for timeframe validation, pagination, CSV/Parquet writing,
  partitioned datasets, and config/env loading.

### Out of Scope

- Streaming market data.
- Paper/live market data event loops.
- Non-stock asset classes.
- Automatic subscription management.
- Database export.

### Expected Files or Modules

- `src/qts/market_data/alpaca.py`
- `scripts/download_data.py`
- `configs/data/alpaca_sip_bars.yaml`
- `tests/unit/market_data/test_alpaca_downloader.py`

### Functional Requirements

- User settings are owned by a config file.
- Credentials are loaded from environment variables or `.env`.
- The default output layout is a partitioned dataset, not one large file.
- Partitioned output is organized by timeframe, symbol, and date.
- Alpaca requests use the full configured interval and apply local
  regular-session filtering to returned intraday rows.
- The downloader requests Alpaca stock bars with `feed=sip`.
- Pagination via `next_page_token` is supported.
- Output includes normalized OHLCV columns and the exact Alpaca timeframe.
- Output can be loaded by `CSVBarProvider` or `LocalParquetProvider`, including
  partitioned dataset directories.

### Testing Requirements

- No-network unit tests with a fake transport.
- Timeframe alias tests.
- Paginated response tests.
- Config/env loading tests.
- CSV and Parquet compatibility tests.
- Partitioned dataset write/read tests.
- Regular-session boundary filtering tests.

### Acceptance Criteria

- `scripts/download_data.py --config configs/data/alpaca_sip_bars.yaml` provides
  a real download command when credentials are present.
- Supported K-line levels are accepted and normalized.
- Tests pass without network access.

### Expected Deliverables

- Configurable Alpaca SIP data downloader.
- Normalized CSV or Parquet partitioned dataset path for backtests.
- Updated user and system documentation.

### Notes for Coding Agent

Keep market data separate from Alpaca brokerage. Do not route downloaded data
through broker adapters.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `README.md`, user manual, and system handbook.
- Add an ADR for the market-data boundary decision.

---

## Major Architecture Phase A: Exchange Calendar and Market Session Service

### Objective

Add one shared exchange calendar/session abstraction for US equity runtime
session checks, replacing weekday-only market-open logic and duplicated
regular-session filtering assumptions.

### Scope

- Add a `qts.calendar` package with:
  - `MarketCalendar` provider protocol,
  - `MarketSession` model,
  - `MarketSessionConfig`,
  - deterministic built-in US equity calendar provider,
  - `MarketSessionService`.
- Support `XNYS` and `NASDAQ` as first US equity exchanges.
- Normalize session boundaries from `America/New_York` to UTC.
- Support regular session only and configurable extended-hours windows.
- Support weekends, common US equity holidays, early closes, and fail-closed
  behavior when a provider cannot resolve a session.
- Add runtime config validation for `market_session`.
- Integrate the service into Alpaca historical session filtering, paper/live
  health checks, live order safety, and broker fallback `is_market_open` logic.

### Out of Scope

- Continuous market-data streaming.
- Broker event streaming.
- Real live order submission.
- Full global exchange coverage.

### Expected Files or Modules

- `src/qts/calendar/`
- `tests/unit/calendar/`
- `src/qts/core/config.py`
- `src/qts/market_data/alpaca.py`
- `src/qts/engines/paper_trading_engine.py`
- `src/qts/engines/live_engine.py`
- `src/qts/monitoring/health.py`
- `src/qts/monitoring/safety.py`

### Testing Requirements

- Unit tests for normal days, weekends, holidays, early closes, timezone
  conversion, regular-session boundaries, extended-hours mode, and fail-closed
  provider behavior.
- Integration-style tests proving live health and order safety use the session
  service.
- Historical filtering tests proving holidays and early closes use the shared
  calendar.

### Acceptance Criteria

- Runtime session checks use `MarketSessionService` instead of ad hoc
  weekday-only logic.
- Session config rejects invalid exchange/provider/timezone combinations.
- Historical downloader filtering uses the shared calendar service.
- Live order safety rejects orders outside the configured tradable session.
- Tests pass without network access.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `DECISIONS.md`, `INTERFACES.md`, and `DATA_MODELS.md`.
- Update README and docs.

---

## Planned Major Architecture Phases

The following phases are intentionally large and should be implemented one at a
time after Phase A is stable:

| Phase | Status | Notes |
|---|---|---|
| Phase B1 - Deterministic Runtime Event Loop and Fake Stream | Complete | Added event-source abstraction, finite fake stream, paper-engine loop wiring, and deterministic tests. |
| Phase B2a - Alpaca Stream Adapter Boundary for Paper Runtime | Complete | Added mockable Alpaca stream payload adapter, paper-engine source factory wiring, config template, and tests. |
| Phase B2b1 - Runtime Reconnect and Heartbeat Policy | Complete | Added bounded reconnect policy, heartbeat/data-gap counters, config plumbing, and deterministic tests. |
| Phase B2b2 - Guarded Live Decision Preview | Complete | Added live dry-run strategy/risk/order-request previews without broker submission. |
| Phase C1 - Normalized Broker Events and Polling Sync | Complete | Added broker event model/helpers, idempotent execution updates, and paper polling fallback. |
| Phase C2 - Vendor Broker Push Adapter Boundaries | Complete | Added mockable Alpaca/IBKR broker order/fill event adapter boundaries without real live submission. |
| Phase C3 - Engine Lifecycle Synchronization Hardening | Complete | Added checkpointed broker-event sync, gap/out-of-order detection, engine reconciliation hooks, and lifecycle double-count protection. |
| Phase D1 - Manual Live Order Submission Safety Envelope | Complete | Added explicit non-dry-run submission gates and a manual `LiveEngine.submit_live_order` path. |
| Phase D2 - Broker-Specific Live Adapter Enablement | Complete | Enabled Alpaca live adapter construction only behind the D1 submission envelope and adapter-specific tests. |
| Phase D3 - Automated Live Decision Submission | Complete | Converts approved live previews into optional broker submissions through D1 gates, kill-switch checks, post-submit reconciliation, and fail-stop controls. |
| Phase E - Chart Reporting and Visual Backtest Diagnostics | Planned | Add optional static chart artifacts for backtest reports. |
| Phase F - Production ML Contracts and Model Governance | Planned | Add model manifests, schema hashes, approval/stage rules, and runtime ML metadata. |

## Major Architecture Phase B1 - Deterministic Runtime Event Loop and Fake Stream

### Goal

Provide a small, deterministic runtime event-loop foundation before connecting
vendor streaming APIs. The first slice is intentionally limited to finite paper
runtime streams so tests can prove ordering, duplicate handling, session
filtering, freshness checks, and dispatch into the existing
strategy/risk/execution path.

### Scope

- Add a `MarketEventSource` protocol and deterministic in-memory fake stream.
- Add a `RuntimeEventLoop` that validates duplicate, stale, out-of-order, and
  out-of-session events before dispatch.
- Allow `PAPER` configs to use `market_data.provider: fake_stream`.
- Wire finite fake-stream runs into `PaperTradingEngine.start(max_events=...)`.
- Add a commented `configs/paper_fake_stream.yaml` template.

### Out of Scope

- Real Alpaca/IBKR websocket adapters.
- Live decision-loop dispatch.
- Broker event stream synchronization beyond existing polling.

### Acceptance Criteria

- Finite fake streams can drive paper trading through the shared strategy,
  risk, execution, brokerage, and portfolio path.
- Duplicate events are skipped, out-of-order events fail closed, stale events
  can fail closed when configured, and session filtering uses
  `MarketSessionService`.
- Tests pass without network access.

## Major Architecture Phase B2a - Alpaca Stream Adapter Boundary for Paper Runtime

### Goal

Introduce a vendor-specific market-data stream adapter boundary without adding
network-dependent websocket code or changing strategy/risk/execution contracts.
This sub-phase makes Alpaca-shaped stream payloads testable through the same
paper runtime event loop introduced in B1.

### Scope

- Add an Alpaca stream client protocol and in-memory Alpaca-shaped stream client
  for deterministic tests.
- Add an `AlpacaStreamEventSource` that maps Alpaca bar/quote stream payloads
  into normalized `Bar` and `Quote` models.
- Allow `PAPER` configs to use `market_data.provider: alpaca_stream`.
- Add a commented `configs/paper_alpaca_stream_mock.yaml` template.
- Wire `PaperTradingEngine` to build the Alpaca stream source from config or an
  injected stream client.

### Out of Scope

- Real websocket transport and credentials-based stream connection.
- Live strategy/risk/execution decision preview.
- Runtime heartbeat/reconnect policy.
- Broker event streams and order lifecycle synchronization.

### Acceptance Criteria

- Alpaca-shaped bar and quote messages normalize to internal domain models.
- Paper runtime can process a finite mock Alpaca stream through the same event
  loop and execution path.
- Missing real stream transport fails closed with a clear configuration error.
- Tests remain deterministic and network-free.

## Major Architecture Phase B2b1 - Runtime Reconnect and Heartbeat Policy

### Goal

Make the runtime market-event loop observable and fail-closed around controlled
stream disconnects and event-heartbeat/data-gap failures before adding guarded
live decision preview.

### Scope

- Add reconnect and heartbeat policy models to the runtime event loop.
- Add reconnect counters, disconnect counters, heartbeat miss counters,
  source-run counters, and stopped-reason status to event-loop results.
- Add `StreamDisconnectedError` for controlled stream disconnect simulation and
  future adapter use.
- Add `market_data.reconnect` and `market_data.heartbeat` config validation.
- Wire paper runtime event loops to read reconnect/heartbeat policies from
  `market_data`.

### Out of Scope

- Real websocket reconnect/backoff sleeping.
- Guarded live strategy/risk/execution decision preview.
- Broker event streams and order lifecycle synchronization.

### Acceptance Criteria

- A controlled stream disconnect fails closed when reconnect is disabled.
- A controlled stream disconnect can reconnect through a source factory when
  reconnect is enabled and attempts remain.
- Heartbeat/data-gap misses are counted, and can either fail closed or warn
  according to config.
- Tests remain deterministic and network-free.

## Major Architecture Phase B2b2 - Guarded Live Decision Preview

### Goal

Allow guarded live dry-run runtimes to process normalized market events through
the same feature, strategy, risk, and order-request construction path used by
paper trading while stopping before broker submission.

### Scope

- Initialize live feature pipeline, data portal, risk engine, and strategies.
- On live bar events, run enabled strategies and risk evaluation.
- Build normalized `OrderRequest` previews for approved risk decisions.
- Validate previews against live order safety gates.
- Record approved or safety-rejected decision previews in health/status output.
- Keep quote-only events stateful but non-ordering for bar-based strategies.

### Out of Scope

- Real live broker order submission.
- Broker event streams and lifecycle synchronization.
- Continuous live stream provider ownership.

### Acceptance Criteria

- Dry-run live bar events can produce safety-approved decision previews without
  calling `broker.submit_order`.
- Unsafe live previews are recorded as rejected instead of submitted.
- Quote-only events update state without creating bar-strategy previews.
- Tests remain deterministic and network-free.

## Major Architecture Phase C - Broker Event Stream and Order Lifecycle Synchronization

### Goal

Synchronize broker-side order and fill lifecycle state through normalized events
so paper and future live runtimes do not depend on ad hoc fill polling alone.

### Split Rationale

The full phase includes normalized event contracts, polling fallback, future
vendor push-stream adapters, restart/recovery behavior, and live-order
lifecycle handling. It is split to keep real live submission out of scope until
the broker-event foundation is stable.

## Major Architecture Phase C1 - Normalized Broker Events and Polling Sync

### Goal

Introduce the internal broker-event contract and make existing polling paths
produce idempotent order/fill synchronization events.

### Scope

- Add `BrokerEventType` and `BrokerEvent` domain models.
- Add execution helpers that convert normalized `Order`, `Fill`, `Account`, and
  `Position` payloads into `BrokerEvent` objects.
- Add `OrderRouter.poll_events()` as a polling fallback over existing
  `Brokerage.list_orders()` and `Brokerage.poll_fills()`.
- Make `ExecutionEngine` consume broker events idempotently.
- Prevent stale or regressive order updates from overwriting newer lifecycle
  state.
- Wire `PaperTradingEngine.poll_broker_updates()` through normalized broker
  events while preserving backward-compatible direct `Order`/`Fill` handling.

### Out of Scope

- Real broker websocket/SSE event transports.
- Live broker order submission.
- Persistent broker-event checkpoints across process restarts.
- New vendor APIs.

### Acceptance Criteria

- Broker event models validate the matching payload type.
- Duplicate broker fill events do not double-apply execution state or portfolio
  state.
- Stale order updates do not regress the tracked order lifecycle.
- Polling fallback emits normalized order and fill events from existing broker
  adapters.
- Tests remain deterministic and network-free.

## Major Architecture Phase C2 - Vendor Broker Push Adapter Boundaries

### Goal

Add mockable broker-event stream adapter boundaries for Alpaca/IBKR order and
fill updates without opening real network streams in tests.

### Scope

- Add broker-event source protocols.
- Add in-memory vendor-shaped broker event clients.
- Normalize vendor order/fill update payloads into `BrokerEvent`.
- Keep real live submission and real network stream ownership out of scope.

### Out of Scope

- Real Alpaca or IBKR websocket/SSE clients.
- Broker stream reconnect/checkpoint orchestration.
- Live broker order submission.
- Persistent event audit storage.

### Acceptance Criteria

- Alpaca-shaped trade update payloads normalize into `BrokerEvent` order and
  incremental fill events.
- IBKR-shaped order update payloads normalize into `BrokerEvent` order and
  incremental fill events.
- In-memory vendor broker-event clients can drive deterministic tests without
  credentials or network access.
- Error payloads fail closed through controlled data errors.
- Tests remain deterministic and network-free.

## Major Architecture Phase C3 - Engine Lifecycle Synchronization Hardening

### Goal

Harden paper/live engine behavior around broker-event gaps, restart
reconciliation, and lifecycle recovery before Phase D production live trading.

### Scope

- Add a deterministic broker-event synchronization loop with duplicate
  suppression, restart checkpoints, out-of-order detection, and optional gap
  fail-closed policy.
- Add paper/live engine methods for synchronizing a `BrokerEventSource` while
  reconciling broker and portfolio state before and after the sync run.
- Expose the latest broker-event sync status in paper/live health output.
- Preserve real live submission as disabled; live sync records lifecycle events
  and reconciliation status only.
- Harden execution lifecycle handling when cumulative broker order updates and
  incremental fill events arrive in either order.
- Keep broker events retryable when application fails before the event is
  successfully processed.

### Out of Scope

- Real broker websocket/SSE transports.
- Persistent checkpoint storage outside process memory.
- Live broker order submission.
- Automatic restart orchestration or sleeping backoff.

### Acceptance Criteria

- Broker-event sync can resume with a checkpoint and skip already processed
  event IDs.
- Broker-event sync detects configured timestamp gaps and fails closed when
  configured to do so.
- Paper and live engines can run sync with reconciliation before and after the
  event source is consumed.
- Matching cumulative order updates and fill events do not double-count filled
  quantity.
- A failed broker event can be retried after missing lifecycle state is
  recovered.
- Tests remain deterministic and network-free.

## Major Architecture Phase D - Production Live-Trading Enablement

### Goal

Enable live order submission only through explicit fail-closed safety gates,
broker-event synchronization, reconciliation, and operator-controlled rollout
steps.

### Split Rationale

Production live trading is intentionally too large and high-risk for one
implementation session. It is split so the submission safety envelope can be
tested independently before any broker-specific live adapter or automated live
decision loop is allowed to send orders.

## Major Architecture Phase D1 - Manual Live Order Submission Safety Envelope

### Goal

Add the smallest live submission surface: a manually supplied `OrderRequest`
can be submitted by `LiveEngine` only when all live safety, account,
reconciliation, and explicit submission gates pass.

### Scope

- Add an explicit `broker.safety.enable_order_submission` gate.
- Add a live order submission safety validator for non-dry-run live configs.
- Add `LiveEngine.submit_live_order(...)` for manually supplied normalized
  `OrderRequest` objects.
- Validate account allowlist, symbol allowlist, market session, order caps,
  fractional policy, and reconciliation immediately before submission.
- Record submission status in live health output and runtime metrics.

### Out of Scope

- Automatically submitting strategy-generated live decision previews.
- Enabling Alpaca or IBKR live adapter construction without injected brokerage.
- Real broker stream transports.
- Persistent order audit storage beyond in-memory health/status output.

### Acceptance Criteria

- Dry-run live configs cannot submit live orders.
- Non-dry-run live configs still cannot submit unless
  `confirm_live_trading=true` and `enable_order_submission=true`.
- Manual live order submission calls `broker.submit_order` only after all
  safety and reconciliation checks pass.
- Submission status appears in live health output.
- Tests remain deterministic and network-free with an injected recording
  brokerage.

## Major Architecture Phase D2 - Broker-Specific Live Adapter Enablement

### Goal

Enable real broker-specific live adapter construction behind the D1 submission
envelope and broker-specific fail-closed tests.

### Scope

- Add live adapter enablement for selected brokers only after credentials,
  base URLs, account allowlists, and paper/live mode checks pass.
- Preserve vendor-specific behavior behind the normalized `Brokerage`
  interface.
- Add mocked broker tests proving live adapter construction and rejected unsafe
  configurations.

### Out of Scope

- Automated strategy-driven live submissions.
- Unbounded reconnect or untested real network stream ownership.

### Acceptance Criteria

- Non-dry-run `LiveEngine` can construct only the selected Alpaca live adapter
  after D1 submission gates pass.
- Ungated Alpaca live adapter configs fail closed before order submission.
- Missing Alpaca live credentials fail during real client construction.
- IBKR live remains out of scope and fail-closed.
- Tests remain deterministic and network-free through injected or patched
  broker clients.

## Major Architecture Phase D3 - Automated Live Decision Submission

### Goal

Allow approved live decision previews to become broker submissions only when a
separate automated-submission gate, lifecycle synchronization, kill-switch, and
monitoring controls are active.

### Scope

- Convert safety-approved live previews into submissions through the D1 path.
- Add operator kill-switch behavior and failure-stop handling.
- Require broker-event sync/reconciliation after submission.

### Out of Scope

- High-frequency trading behavior.
- Multi-broker smart routing.

### Acceptance Criteria

- Automated live submission remains disabled unless
  `enable_automated_submission=true`.
- `automated_submission_kill_switch=true` blocks automated submissions.
- Safety-approved live previews submit through `LiveEngine.submit_live_order`
  only after D1 gates pass and the live engine is running.
- Automated submissions reconcile after broker submission.
- Submission errors or post-submit reconciliation mismatches stop further
  automated submissions and report critical health.
- Tests remain deterministic and network-free.
