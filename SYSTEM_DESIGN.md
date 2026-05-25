# SYSTEM_DESIGN.md

# Modular Quantitative Trading Strategy Development System

## 1. Project Overview

This project is a lightweight, modular quantitative trading system for:

- quantitative research,
- standardized backtesting,
- paper trading,
- future guarded live trading.

The system is designed for an individual developer or a small team. It should follow practical industry-style architecture without becoming an enterprise-scale platform.

The central design goal is consistency: the same strategy, risk, execution, and portfolio logic should be reusable across backtesting, paper trading, and future live trading. Runtime-specific behavior should be isolated behind market data providers, clocks, and brokerage adapters.

## 2. Core Goals

1. **Convenient strategy development**
   - Strategies generate signals, target positions, or trade intents.
   - Strategies do not submit orders directly.
   - Strategies do not mutate portfolio, account, cash, or position state.

2. **Reusable indicator and feature layer**
   - Indicators and features are implemented once and reused across:
     - rule-based strategies,
     - ML dataset construction,
     - ML inference,
     - backtesting,
     - paper trading,
     - live trading.
   - The feature layer supports batch computation first and leaves room for online/stateful updates.

3. **Unified signal path**
   - Rule-based strategies and ML-based strategies are equivalent runtime signal generators.
   - Both output normalized `Signal`, `TargetPosition`, or `TradeIntent` domain objects.

4. **Separated market data and brokerage**
   - Market data is owned by `market_data/`.
   - Order submission and account interaction are owned by `brokers/`.
   - Even when one vendor provides both APIs, such as Alpaca, the system keeps these interfaces separate.

5. **Broker-agnostic execution**
   - The execution layer routes normalized order requests to the configured `Brokerage`.
   - It does not depend on Alpaca, Futu, Polygon, or any vendor API object.

6. **Backtest brokerage treated as a real brokerage implementation**
   - `BacktestBrokerage` implements the same `Brokerage` interface as real broker adapters.
   - It simulates order acceptance, rejection, lifecycle, fills, slippage, commission, cash, positions, and session behavior.

7. **Independent risk management**
   - Risk consumes strategy output and produces approved or rejected order intents.
   - Risk is independent of strategy type.
   - Position sizing belongs primarily to the risk layer.

8. **Phase-by-phase implementation**
   - The system must be implemented in clearly bounded phases.
   - Documentation files must be updated after each implementation phase to prevent context drift.

## 3. Non-Goals for Initial Implementation

The initial implementation must not attempt to build:

- high-frequency trading infrastructure,
- exchange colocation or nanosecond event processing,
- full order book simulation,
- options, futures, crypto, or complex margin trading,
- distributed compute infrastructure,
- multi-broker smart order routing,
- production-grade web dashboard,
- automatic strategy optimization,
- unguarded live trading.

## 4. Target Users

Primary users:

- individual quantitative developer,
- small research team,
- developer preparing a portfolio-grade trading system,
- developer who wants consistent backtest, paper trading, and live trading architecture.

Secondary users:

- AI coding agents continuing implementation across multiple sessions,
- reviewers evaluating architecture and maintainability.

## 5. Main Use Cases

| Use Case | Description |
|---|---|
| Run local research | Load local historical data, compute indicators, inspect features, and test strategy ideas. |
| Download historical bars | Download Alpaca SIP historical K-line data into normalized local CSV or Parquet partitioned datasets with explicit local regular-session filtering. |
| Run standardized backtest | Execute a strategy through the same signal → risk → execution → brokerage → portfolio path used by paper/live modes. |
| Compare strategies | Run multiple strategies under the same data, cost, slippage, and risk assumptions. |
| Train ML models | Build datasets, labels, splits, leakage checks, train models, and register artifacts. |
| Run ML strategy inference | Load a registered model, compute runtime features, predict, and convert predictions into normalized trade intents. |
| Paper trade through broker adapters | Use live/near-real-time data with Alpaca or IBKR paper brokerage while reusing the same strategy, risk, execution, and portfolio logic. |
| Prepare for live trading | Add reconciliation, health checks, alerts, recovery behavior, and explicit safety gates before live mode is enabled. |

## 6. High-Level Architecture

```text
                 ┌─────────────────────┐
                 │      Configs        │
                 └──────────┬──────────┘
                            │
┌──────────────┐   ┌────────▼────────┐   ┌────────────────┐
│ Market Data  │──▶│ Feature Layer   │──▶│ Strategy Layer │
│ Providers    │   │ Indicators      │   │ Rule / ML      │
└──────┬───────┘   └─────────────────┘   └───────┬────────┘
       │                                          │ Signal / TradeIntent
       │                                  ┌───────▼────────┐
       │                                  │ Risk Layer     │
       │                                  └───────┬────────┘
       │                                  Approved OrderIntent
       │                                  ┌───────▼────────┐
       │                                  │ Execution      │
       │                                  └───────┬────────┘
       │                                  OrderRequest / Order
       │                                  ┌───────▼────────┐
       └─────────────────────────────────▶│ Brokerage      │
 Current bar/quote for fill simulation    │ Backtest/Alpaca/IBKR│
                                          └───────┬────────┘
                                                  │ Fill
                                          ┌───────▼────────┐
                                          │ Portfolio      │
                                          └───────┬────────┘
                                                  │ Snapshot / Ledger
                                          ┌───────▼────────┐
                                          │ Reporting      │
                                          └────────────────┘
```

## 7. Module Decomposition

### `domain/`

Owns stable business data models and enums.

Examples:

- `Bar`
- `Quote`
- `Trade`
- `Signal`
- `TargetPosition`
- `TradeIntent`
- `RiskDecision`
- `OrderRequest`
- `Order`
- `Fill`
- `Position`
- `Account`
- `PortfolioSnapshot`

Rules:

- No vendor-specific objects.
- No I/O.
- No strategy logic.
- No broker API calls.
- Must remain stable and widely reusable.

### `core/`

Owns shared infrastructure:

- config loading and validation,
- clocks,
- event models and event bus,
- lifecycle interfaces,
- logging setup,
- exceptions,
- common result/error types.

Rules:

- Must not depend on strategies, broker implementations, or vendor clients.
- Can be imported by all modules.

### `calendar/`

Owns exchange calendar and market-session behavior:

- `MarketCalendar` provider contract,
- built-in US equity session provider,
- `MarketSessionService`,
- regular and extended-hours session checks,
- holidays, early closes, timezone conversion, and fail-closed semantics.

Rules:

- Must not load market data or submit orders.
- Runtime modules must call this shared service instead of duplicating
  weekday-only market-open logic.

### `market_data/`

Owns market data interfaces and implementations:

- `MarketDataProvider`,
- `DataPortal`,
- local Parquet/CSV providers,
- Alpaca SIP historical bar downloader,
- in-memory runtime data portal for paper/live market-event state,
- Alpaca stream adapter boundary,
- historical data loaders,
- replay data provider,
- live data provider abstractions,
- data normalization,
- corporate action adjustment policy,
- symbol mapping.

Rules:

- Does not submit orders.
- Does not own brokerage state.
- Does not call execution directly.
- Vendor stream payloads must be normalized to internal `Bar`/`Quote` models
  before leaving this layer.
- Paper/live runtime data state should use the shared
  `InMemoryRuntimeDataPortal` instead of engine-local portal implementations.

### `features/`

Owns reusable indicators and feature pipelines:

- SMA, EMA, RSI, MACD, Bollinger Bands, ATR, VWAP,
- returns, volatility, volume features,
- batch feature computation,
- online/stateful indicator interfaces,
- feature schema validation.

Rules:

- Indicators are not hardcoded inside strategies.
- Feature logic must be reusable for both ML training and runtime inference.

### `strategies/`

Owns runtime strategies:

- rule-based strategies,
- ML-based strategy adapters,
- signal generation,
- target position generation,
- trade intent generation.

Rules:

- Strategies do not submit broker orders.
- Strategies do not modify account or portfolio state.
- Strategies may read market data, computed features, and portfolio snapshots if explicitly provided by the engine.
- Strategies output normalized domain objects.

### `ml/`

Owns offline ML workflows:

- dataset construction,
- label generation,
- train/validation/test splitting,
- walk-forward validation,
- leakage checks,
- model training,
- model evaluation,
- model registry,
- model manifests and schema hashes,
- model approval stage transitions,
- runtime model diagnostics,
- inference pipeline utilities.

Rules:

- Training is offline.
- A trained model is not itself a complete strategy.
- Runtime ML strategy lives in `strategies/` and uses registered models from `ml/`.
- Newly saved model artifacts include a local manifest contract so runtime
  inference can verify feature-schema compatibility before prediction.
- Runtime ML inference can be configured to require approved models or a
  specific set of allowed manifest stages.
- Runtime predictions, ML strategy signals, backtest reports, and runtime
  health diagnostics carry enough model contract metadata to trace which
  manifest and feature schema produced a decision.

### `risk/`

Owns risk evaluation and sizing:

- risk rules,
- risk engine,
- risk result objects,
- position sizing,
- exposure checks,
- buying power checks,
- daily loss limits,
- cooldown rules,
- trading session rules,
- symbol restrictions.

Rules:

- Risk consumes normalized strategy output.
- Risk is independent of whether the signal came from a rule-based or ML strategy.
- Risk can approve, reject, or modify trade intents.

### `execution/`

Owns order execution workflow:

- execution engine,
- order request builder,
- order manager,
- order router,
- fill handler,
- broker lifecycle event helpers,
- execution policy.

Rules:

- Does not contain strategy logic.
- Does not contain broker-specific API details.
- Talks only to the normalized `Brokerage` interface.
- Consumes normalized broker lifecycle events idempotently.

### `brokers/`

Owns normalized brokerage interface and broker implementations:

- `Brokerage` interface,
- `brokers/factory.py`,
- `brokers/backtest/BacktestBrokerage`,
- `brokers/alpaca/AlpacaBrokerage`,
- `brokers/ibkr/IBKRBrokerage`.

Rules:

- Broker selection belongs in `brokers.factory`; engines should request a
  brokerage through the factory and should not import concrete adapter classes.
- The factory constructs broker adapters but does not connect them, read
  configuration files, mutate `BrokerConfig`, or submit orders.
- Concrete broker behavior is isolated here.
- Backtest brokerage is a first-class broker implementation.
- Broker adapters may use low-level clients from `integrations/`.
- Alpaca live adapter construction is allowed only behind explicit D1 live
  confirmation and submission gates; IBKR live remains fail-closed.

### `integrations/`

Owns low-level vendor clients:

- Alpaca trading client,
- IBKR Web API client,
- Alpaca market data client,
- Alpaca stream client,
- Alpaca broker trade-update event client boundary,
- IBKR broker order-update event client boundary,
- Futu client,
- Polygon client.

Rules:

- Vendor API models must be converted into internal domain models before leaving adapter boundaries.
- Strategy, risk, execution, and portfolio modules must not import vendor SDKs directly.
- Broker push-style order/fill payloads must normalize to `BrokerEvent` before
  they are consumed by execution or engines.

### `portfolio/`

Owns portfolio accounting:

- position accounting,
- cash ledger,
- trade ledger,
- realized PnL,
- unrealized PnL,
- average cost,
- account snapshots,
- equity curve,
- broker reconciliation.

Rules:

- Backtest updates come from simulated fills.
- Paper/live updates come from broker fills and reconciliation.
- Internal portfolio state remains conceptually separate from broker state.

### `engines/`

Owns runtime orchestration:

- `BacktestEngine`,
- `PaperTradingEngine`,
- `LiveEngine`,
- `RuntimeDecisionPipeline`,
- runtime market-event loop primitives and event-source contracts.

Rules:

- Engines wire modules together.
- Engines select clock, data provider, broker implementation, strategy, risk, execution, portfolio, and reporter based on configuration.
- Engines do not contain detailed strategy, broker, or risk logic.
- Shared feature, strategy, and risk evaluation should run through
  `RuntimeDecisionPipeline` so backtest, paper, and guarded live preview paths
  use the same market-event decision sequence.
- `RuntimeDecisionPipeline` stops at risk decisions. It does not import
  concrete broker adapters, submit orders, read configuration files, or connect
  to external services.
- Runtime market-event loops must validate duplicate, stale, out-of-order, and
  out-of-session events before dispatching to engine callbacks.
- Runtime market-event loops expose controlled stream disconnect, reconnect,
  and heartbeat/data-gap status without embedding vendor transport details in
  engine code.
- Paper/live broker-event synchronization must use normalized `BrokerEvent`
  sources, in-process checkpoints, gap/out-of-order policy checks, and
  reconciliation before and after sync.
- Guarded live dry-run event handling may produce decision previews, but it must
  stop before broker submission and validate live safety gates.
- Manual live submission must use `LiveEngine.submit_live_order(...)` and must
  require explicit non-dry-run, confirmation, submission, account, order, market
  session, and reconciliation gates before calling `broker.submit_order`.
- Non-dry-run live brokerage construction is limited to the selected Alpaca
  adapter and requires those same D1 gates.
- Automated live submission may only convert safety-approved decision previews
  through the D1 submission path when an additional automation gate is enabled
  and the automated kill switch is open. The live engine must be running before
  automation submits. Submission failures must stop further automation.

### `reporting/`

Owns analytics and outputs:

- performance metrics,
- trade analysis,
- equity curve,
- drawdown,
- benchmark comparison,
- optional static SVG plots,
- report exports.

### `monitoring/`

Owns operational visibility:

- health checks,
- metrics logging,
- alerts,
- error reporting,
- runtime status.

### `research/`

Owns research workflows:

- experiments,
- parameter sweeps,
- strategy comparisons,
- hypothesis testing.

### `utils/`

Owns only small cross-cutting helpers.

Rules:

- Must not become a dumping ground.
- If a helper grows business meaning, move it to a proper module.

## 8. Recommended Project Directory Structure

```text
quant-trading-system/
  README.md
  pyproject.toml
  .env.example
  .gitignore

  configs/
    base.yaml
    backtest.yaml
    data/
      alpaca_sip_bars.yaml
    paper_alpaca.yaml
    paper_ibkr.yaml
    live_alpaca.yaml
    data/
    brokers/
    strategies/
    risk/
    ml/

  src/
    qts/
      domain/
      core/
      calendar/
      market_data/
      features/
      strategies/
      ml/
      risk/
      execution/
      brokers/
        backtest/
        alpaca/
        ibkr/
      integrations/
        alpaca/
        ibkr/
        futu/
        polygon/
      portfolio/
      engines/
      reporting/
      monitoring/
      research/
      utils/
      cli.py

  scripts/
    download_data.py
    run_backtest.py
    run_paper_trading.py
    run_live_trading.py
    train_model.py
    generate_report.py

  notebooks/
    01_data_exploration.ipynb
    02_feature_research.ipynb
    03_strategy_research.ipynb
    04_ml_model_research.ipynb

  data/
    raw/
    processed/
    features/
    external/

  artifacts/
    models/
    backtests/
    reports/
    plots/
    logs/

  tests/
    unit/
    integration/
    fixtures/

  docs/
    architecture.md
    data_interface.md
    strategy_interface.md
    risk_engine.md
    execution_engine.md
    broker_interface.md
    backtest_brokerage.md
    ml_workflow.md
    runbooks.md
```

## 9. Dependency Direction

Allowed high-level dependency direction:

```text
domain        <- imported by nearly all modules
core          <- imported by nearly all modules
market_data   -> domain, core
features      -> domain, core
strategies    -> domain, core, features
ml            -> domain, core, features
risk          -> domain, core, portfolio
execution     -> domain, core, brokers
brokers       -> domain, core, integrations
portfolio     -> domain, core
engines       -> all orchestration dependencies
reporting     -> domain, portfolio, backtest results
monitoring    -> core and runtime status objects
research      -> data, features, strategies, reporting
```

Prohibited dependencies:

- `strategies/` must not import concrete brokers.
- `risk/` must not import concrete strategies.
- `execution/` must not import vendor SDKs.
- `portfolio/` must not import concrete strategy logic.
- `domain/` must not import application modules.
- `features/` must not import strategies.

## 10. Main Data Flow

1. Market data provider emits or returns normalized `Bar`, `Quote`, or `Trade`.
2. Feature pipeline computes indicators and feature records.
3. Strategy receives market data, feature data, and optional portfolio snapshot.
4. Strategy emits `Signal`, `TargetPosition`, or `TradeIntent`.
5. Risk engine evaluates the strategy output.
6. Risk engine approves, rejects, or modifies the intent.
7. Execution engine converts approved intent into `OrderRequest`.
8. Order router submits request to configured `Brokerage`.
9. Brokerage creates `Order` state and eventually `Fill` events.
10. Execution normalizes broker polling or future push updates into
   `BrokerEvent` lifecycle events.
11. Portfolio applies fills and updates positions, cash, ledgers, and snapshots.
12. Reporter consumes portfolio snapshots, trades, fills, and backtest metadata.

## 11. Runtime Flow: Backtesting

Runtime components:

- historical or replay market data provider,
- `ReplayClock`,
- reusable feature pipeline,
- strategy,
- risk engine,
- execution engine,
- `BacktestBrokerage`,
- portfolio,
- reporter.

Flow:

1. Load backtest configuration.
2. Initialize replay clock and historical data provider.
3. Initialize portfolio with starting cash.
4. Initialize strategy, risk engine, execution engine, and backtest brokerage.
5. For each replayed bar or event:
   - update clock,
   - update feature state,
   - pass data/features to strategy,
   - collect signals/intents,
   - run risk checks and sizing,
   - build and route order requests,
   - allow `BacktestBrokerage` to simulate fills using current or next eligible market event according to configured fill policy,
   - apply fills to portfolio,
   - mark portfolio to market,
   - record snapshots.
6. Generate `BacktestResult`, metrics, ledgers, optional static plots, and report.

## 12. Runtime Flow: Paper Trading

Runtime components:

- live or near-real-time market data provider,
- `RealClock`,
- reusable feature pipeline,
- same strategy interface,
- same risk engine,
- same execution engine,
- `AlpacaBrokerage` or `IBKRBrokerage` configured for paper trading,
- portfolio,
- monitoring and reconciliation.

Flow:

1. Load paper trading configuration.
2. Initialize live data stream/provider.
3. Initialize the configured paper brokerage adapter.
4. Load or initialize portfolio state.
5. Receive market data events.
6. Update online features.
7. Generate strategy output.
8. Evaluate risk and sizing.
9. Route approved order requests to the configured paper brokerage.
10. Consume normalized broker order/fill events from polling fallback or future
    broker event streams.
11. Update portfolio from real broker fills.
12. Periodically reconcile internal portfolio with broker account and positions.
13. Log and alert errors.

## 13. Runtime Flow: Future Live Trading

Live trading uses the same flow as paper trading with stricter controls:

- explicit `live_enabled: true`,
- separate credentials,
- environment guardrails,
- account and symbol allowlists,
- maximum order size caps,
- daily kill switch,
- reconciliation checks before trading,
- health checks and alerts,
- explicit `enable_order_submission: true` before any broker submission,
- selected broker-specific live adapter construction only after the same
  explicit submission gates pass,
- explicit `enable_automated_submission: true` and an open automated kill
  switch before strategy decisions can submit automatically,
- dry-run mode recommended before enabling real order submission.

Automated strategy-driven live submission is supported only for externally
supplied live market events after the explicit automated gate is enabled.
Continuous live stream ownership remains future work.

## 14. Configuration Strategy

Configuration files are layered:

1. `configs/base.yaml`
2. mode-specific file:
  - `configs/backtest.yaml`
   - `configs/data/alpaca_sip_bars.yaml`
   - `configs/paper_alpaca.yaml`
   - `configs/paper_ibkr.yaml`
   - `configs/live_alpaca.yaml`
3. optional environment variables and `.env`
4. optional CLI overrides.

Configuration must include:

- runtime mode,
- symbols,
- timeframe,
- date range,
- market data provider,
- broker implementation,
- strategy config,
- risk config,
- execution config,
- portfolio starting state,
- slippage and commission assumptions,
- output paths,
- safety gates for live trading.

Secrets must not be stored in YAML. Use environment variables or `.env`.

## 15. Error Handling Strategy

Use explicit exception categories:

| Category | Examples |
|---|---|
| Configuration errors | missing required config, invalid enum, invalid path |
| Data errors | missing columns, duplicate timestamps, invalid timezone |
| Feature errors | insufficient lookback, schema mismatch |
| Strategy errors | invalid signal, unsupported symbol |
| Risk errors | invalid sizing, rule conflict |
| Execution errors | invalid order request, router failure |
| Broker errors | API rejection, connection failure, order not found |
| Portfolio errors | negative cash when forbidden, unknown fill |
| Reconciliation errors | broker state mismatch |
| Live safety errors | live mode guard failed |

Backtest mode may fail fast for invalid setup. Paper/live mode should report errors, avoid unsafe order submission, and continue only when safe.

## 16. Logging Strategy

Logging should be structured and concise.

Minimum logs:

- run start/end,
- configuration summary without secrets,
- data loading summary,
- strategy signal summary,
- risk decision summary,
- order submission and status updates,
- fills,
- portfolio snapshots at configured frequency,
- errors and warnings,
- reconciliation results.

Backtests should write logs under `artifacts/logs/`. Paper/live logs should be suitable for monitoring and alerting.

## 17. Testing Strategy

Testing layers:

| Layer | Test Type |
|---|---|
| `domain/` | unit tests for validation and serialization |
| `core/` | config and clock tests |
| `market_data/` | data normalization, schema, replay order |
| `features/` | known-value indicator tests |
| `strategies/` | deterministic signal generation tests |
| `risk/` | approve/reject/modify decision tests |
| `execution/` | order request building and lifecycle tests |
| `brokers/backtest/` | fill simulation, cash/position checks, rejection tests |
| `portfolio/` | accounting and PnL tests |
| `engines/` | end-to-end backtest smoke tests |
| `reporting/` | metric calculation tests |
| `integrations/` | mocked vendor API tests |

Acceptance tests should prove that an SMA crossover strategy can run end-to-end in backtest mode.

## 18. Extensibility Strategy

Extension points:

- new market data provider,
- new broker adapter,
- new feature pipeline,
- new indicator,
- new strategy,
- new risk rule,
- new position sizing model,
- new slippage or commission model,
- new reporter/exporter,
- new ML model framework,
- new runtime engine.

Extension rule:

- New implementations should conform to existing interfaces.
- Vendor-specific data must be converted to internal domain models at module boundaries.
- Public interface changes must be documented in `INTERFACES.md`.

## 19. Future Expansion Points

Potential later additions:

- second-level bars and quote-based backtests,
- more realistic partial fill models,
- corporate action adjustment service,
- benchmark and factor exposure reporting,
- model monitoring,
- dashboard,
- multi-account support,
- additional broker adapters,
- scheduled batch research jobs,
- automated walk-forward strategy evaluation,
- robust deployment packaging.

## 20. AI Coding Agent Operating Rules

Every new implementation session must first read:

1. `PROJECT_STATE.md`
2. `PHASE_PLAN.md`
3. `DECISIONS.md`
4. `INTERFACES.md`
5. `DATA_MODELS.md`
6. `CHANGELOG.md`

The agent must:

- inspect the existing repository before making changes,
- continue from the next unfinished task,
- avoid restarting from scratch,
- respect phase boundaries,
- avoid implementing future-phase functionality unless required for current-phase testability,
- prefer small complete functionality over broad incomplete functionality,
- update state and changelog after each phase,
- record new architectural assumptions in `DECISIONS.md`.
