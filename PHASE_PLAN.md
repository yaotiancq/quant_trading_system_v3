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
K-line data into normalized CSV or Parquet files that existing local providers
can read.

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
- Write normalized CSV output compatible with `CSVBarProvider` and normalized
  Parquet output compatible with `LocalParquetProvider`.
- Add tests for timeframe validation, pagination, CSV/Parquet writing, and
  config/env loading.

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
- The default output path is derived from a filename template, not a fixed
  extension.
- The downloader requests Alpaca stock bars with `feed=sip`.
- Pagination via `next_page_token` is supported.
- Output includes normalized OHLCV columns and the exact Alpaca timeframe.
- Output can be loaded by `CSVBarProvider` or `LocalParquetProvider`.

### Testing Requirements

- No-network unit tests with a fake transport.
- Timeframe alias tests.
- Paginated response tests.
- Config/env loading tests.
- CSV and Parquet compatibility tests.

### Acceptance Criteria

- `scripts/download_data.py --config configs/data/alpaca_sip_bars.yaml` provides
  a real download command when credentials are present.
- Supported K-line levels are accepted and normalized.
- Tests pass without network access.

### Expected Deliverables

- Configurable Alpaca SIP data downloader.
- Normalized CSV or Parquet output path for backtests.
- Updated user and system documentation.

### Notes for Coding Agent

Keep market data separate from Alpaca brokerage. Do not route downloaded data
through broker adapters.

### Required Updates

- Update `PROJECT_STATE.md`.
- Update `CHANGELOG.md`.
- Update `README.md`, user manual, and system handbook.
- Add an ADR for the market-data boundary decision.
