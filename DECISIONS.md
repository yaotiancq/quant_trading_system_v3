# DECISIONS.md

# Architectural Decision Record

## ADR-001: Separate Market Data from Brokerage

### Context

Some vendors, such as Alpaca, provide both market data and trading APIs. A simple implementation could let a broker adapter load data and submit orders.

### Decision

Market data access and brokerage execution must be separate interfaces and modules.

### Rationale

Backtesting, paper trading, and live trading require different combinations of data and execution. Keeping them separate allows local Parquet data, Alpaca data, Futu data, Polygon data, and broker APIs to be combined without changing strategies.

### Consequences

- More interfaces are required.
- Vendor clients may exist in multiple adapter modules.
- Architecture remains cleaner and easier to test.

### Alternatives Considered

- Let broker adapters own market data loading.
- Use a single vendor-specific adapter for everything.

---

## ADR-002: Treat BacktestBrokerage as a Real Brokerage Implementation

### Context

Backtests need simulated execution. A common shortcut is to let the backtest engine directly fill orders and update positions.

### Decision

`BacktestBrokerage` must live under the broker layer and implement the same `Brokerage` interface as real broker adapters.

### Rationale

This keeps backtesting, paper trading, and live trading consistent. Execution code can route orders to any brokerage implementation without knowing whether it is simulated or real.

### Consequences

- Backtest brokerage must simulate lifecycle, fills, cash, positions, and account behavior.
- The backtest engine remains cleaner.
- Fill models can be tested independently.

### Alternatives Considered

- Put fill simulation directly inside `BacktestEngine`.
- Let portfolio create fills without a broker abstraction.

---

## ADR-003: Keep Strategies Broker-Agnostic

### Context

Strategies could directly call a broker API for convenience, but that would make them hard to reuse across runtime modes.

### Decision

Strategies may only generate `Signal`, `TargetPosition`, or `TradeIntent` objects. They must not submit orders or mutate account state.

### Rationale

This preserves reusability and makes strategies testable. The same strategy can run in backtest, paper, or live modes.

### Consequences

- Strategy output must be converted by risk and execution layers.
- Strategy code remains focused on decision logic.

### Alternatives Considered

- Strategy submits broker orders directly.
- Strategy directly updates portfolio state.

---

## ADR-004: Keep Risk Independent from Strategy Type

### Context

The system must support both rule-based and ML-based strategies.

### Decision

Risk operates on normalized strategy outputs, not concrete strategy classes.

### Rationale

Risk rules should not care whether a trade came from SMA crossover, RSI mean reversion, or an ML model. This allows consistent exposure, sizing, and safety controls.

### Consequences

- Rule-based and ML strategies must emit compatible domain objects.
- Risk logic is reusable across strategy families.

### Alternatives Considered

- Implement strategy-specific risk handling.
- Let strategies handle their own sizing and exposure limits.

---

## ADR-005: Separate ML Offline Training from Runtime ML Strategy Inference

### Context

ML models require offline dataset building, labels, splitting, training, and validation. Runtime trading requires fast inference and signal conversion.

### Decision

Offline ML workflows belong in `ml/`. Runtime ML strategy adapters belong in `strategies/` and use registered models for inference.

### Rationale

A trained model is not a complete trading strategy. The runtime strategy is responsible for feature preparation, prediction interpretation, and normalized output generation.

### Consequences

- Training-serving consistency must be explicitly enforced.
- Feature schemas and model metadata are required.
- ML strategies can reuse the same signal/risk/execution path as rule-based strategies.

### Alternatives Considered

- Treat the model artifact as the strategy.
- Put all ML logic inside the strategy layer.

---

## ADR-006: Use Unified Internal Domain Models Instead of Vendor API Objects

### Context

Vendor SDKs use different object models and field names.

### Decision

All external API objects must be converted into internal domain models before crossing adapter boundaries.

### Rationale

This prevents vendor coupling from leaking into strategy, risk, execution, portfolio, and reporting modules.

### Consequences

- Adapter mapping code is required.
- Domain models become the stable contract across the system.
- Switching vendors becomes easier.

### Alternatives Considered

- Pass vendor objects through the system.
- Build one internal model per vendor.

---

## ADR-007: Use Configuration to Switch Runtime Modes

### Context

Backtesting, paper trading, and live trading should reuse most application logic.

### Decision

Runtime mode, market data provider, broker implementation, strategy, risk rules, and execution settings are selected by configuration.

### Rationale

This allows switching between backtest, paper, and future live trading without changing strategy, risk, or execution code.

### Consequences

- Config validation becomes important.
- Factories are needed to instantiate components from config.
- Live trading must have explicit safety gates.

### Alternatives Considered

- Separate scripts with hardcoded dependencies.
- Separate code paths for every runtime mode.

---

## ADR-008: Maintain Phase-by-Phase State Documents to Prevent Context Drift

### Context

The project may be implemented by AI coding agents over multiple sessions. Long projects are vulnerable to context drift and repeated restarts.

### Decision

The project must maintain `PROJECT_STATE.md`, `PHASE_PLAN.md`, `DECISIONS.md`, `INTERFACES.md`, `DATA_MODELS.md`, and `CHANGELOG.md`.

### Rationale

These documents preserve architectural consistency and tell future coding agents where to continue.

### Consequences

- Every phase must update project state and changelog.
- Public interface or model changes must update the appropriate design documents.
- Slight documentation overhead is accepted to reduce project drift.

### Alternatives Considered

- Rely only on chat history.
- Rely only on repository code.

---

## ADR-009: Start with Minute-Level Bars, Preserve Path to Second-Level Data

### Context

The system should support second-level trading frequency requirements eventually, but initial implementation should stay lightweight.

### Decision

The first implementation target is minute-level bars. Domain models and interfaces must not prevent second-level bars, quotes, or trades later.

### Rationale

Minute-level bars are easier to test and implement while preserving a realistic path toward higher-frequency data.

### Consequences

- Initial backtests are bar-driven.
- Quote/tick support can be added later through existing market data interfaces.
- Fill simulation should be configurable and explicit.

### Alternatives Considered

- Start directly with tick-level or order-book simulation.
- Limit the system permanently to daily bars.

---

## ADR-010: Use Local Parquet as First Historical Data Format

### Context

Local historical data is needed for reproducible backtests.

### Decision

Parquet is the primary historical data format. CSV is supported for fixtures and debugging.

### Rationale

Parquet is efficient and common for research workflows. CSV is convenient for small tests.

### Consequences

- The data layer must validate schema and normalize timestamps.
- Test fixtures can remain simple CSV files.

### Alternatives Considered

- Use only CSV.
- Use a database as the first storage backend.

---

## ADR-011: Default Backtest Fill Policy Must Avoid Same-Bar Look-Ahead

### Context

If a strategy computes a signal using bar close, filling at the same bar close introduces look-ahead bias unless explicitly modeled as a research approximation.

### Decision

Default market-order fill policy should be `next_bar_open` for bar-based backtests. Other policies may be configured explicitly.

### Rationale

This is a conservative and common default for bar-based systems. It avoids using information that would not have been known before the order decision.

### Consequences

- Results may differ from same-close simplified backtests.
- Users can still configure `next_bar_close`, `next_bar_typical_price`, or quote-based fills for specific research assumptions.

### Alternatives Considered

- Always fill at current close.
- Always fill at next close.
- Require quote data for all fills.

---

## ADR-012: Position Sizing Belongs Primarily to Risk Layer

### Context

Strategies may express direction or conviction, but portfolio-wide exposure and buying power controls should be centralized.

### Decision

Position sizing is primarily owned by the risk layer through `PositionSizer`.

### Rationale

Centralized sizing ensures consistent risk controls across strategies and runtime modes.

### Consequences

- Strategy outputs may be unsized signals.
- Risk can modify trade sizes or reject them.
- Strategy-specific sizing may exist only when explicitly documented and still subject to risk approval.

### Alternatives Considered

- Let each strategy own all sizing.
- Let execution layer determine sizing.

---

## ADR-013: Use Standard-Library Dataclasses for Phase 1 Domain Models

### Context

Phase 1 needs stable domain models, config loading, clocks, exceptions, and tests.
The local development environment does not currently include third-party runtime
dependencies such as Pydantic, PyYAML, or pytest.

### Decision

Implement the Phase 1 domain model layer with standard-library dataclasses and
explicit validation. Implement config loading with optional PyYAML support when
available and a small internal YAML subset parser for the repository's own
configuration templates.

### Rationale

This keeps the initial foundation runnable and testable in a minimal local
environment while preserving the documented public domain contracts. It also
avoids making basic imports depend on network-installed packages.

### Consequences

- Domain validation is explicit in model `__post_init__` methods.
- Tests can run with `unittest` without installing pytest.
- The config parser is intentionally limited and should not grow into a general
  YAML implementation; if config complexity grows, PyYAML should become a real
  runtime dependency.

### Alternatives Considered

- Require Pydantic for domain models immediately.
- Require PyYAML for all config loading immediately.
- Delay model/config implementation until third-party dependencies are installed.

---

## ADR-014: Keep Phase 2 Features Row-Oriented and Parquet Dependencies Optional

### Context

Phase 2 needs local historical data loading, deterministic replay, and reusable
batch features. The current local environment can run standard-library tests but
does not include data-science packages by default.

### Decision

Represent Phase 2 feature output as row-oriented `list[dict]` data inside the
existing `FeatureFrame.features` field. Keep CSV support fully standard-library.
Implement the local Parquet provider using pandas or pyarrow when one is
installed, and expose those packages as optional `data` dependencies.

### Rationale

This preserves the documented `FeatureFrame` contract without forcing pandas
objects into public interfaces. It keeps local fixtures and tests runnable in a
minimal environment while leaving a direct path to efficient Parquet data.

### Consequences

- CSV fixtures are the guaranteed Phase 2 test path.
- Parquet loading is implemented but requires installing optional dependencies.
- Later phases can add dataframe-native adapters without changing the public
  domain model.

### Alternatives Considered

- Require pandas and pyarrow as hard runtime dependencies immediately.
- Store `FeatureFrame.features` as a pandas DataFrame.
- Delay Parquet provider implementation until a dependency install step exists.

---

## ADR-015: Phase 3 Strategies Emit Signals and Risk Owns Final Sizing

### Context

Phase 3 introduces the first trading decision path without implementing
execution, brokers, fills, or portfolio accounting. Strategies need to be useful
for future backtests while staying broker-agnostic and reusable.

### Decision

The Phase 3 example strategies emit `Signal` objects only. The risk layer
converts `Signal` and `TargetPosition` inputs into `TradeIntent` objects and
applies position sizing before evaluating rules. The default risk engine may
modify an intent to satisfy a configured max-position-notional rule, and it
rejects intents that fail symbol, session, cooldown, daily-loss, gross-exposure,
symbol-weight, or buying-power checks.

Buying-power checks use `PortfolioSnapshot.metadata["buying_power"]` when
present and fall back to `PortfolioSnapshot.cash` until portfolio/account
integration adds a first-class source.

### Rationale

This preserves the documented strategy/risk boundary and keeps the first
strategies deterministic and easy to test. It also lets later phases reuse the
same normalized risk decisions when execution and broker adapters are added.

### Consequences

- Phase 3 can test strategy and risk behavior without routing orders.
- Strategies remain unsized by default.
- Risk decisions include sizing details and rule reason codes.
- Portfolio snapshots must provide enough context for risk checks; richer
  account-derived buying power can be introduced later without changing the
  `RiskEngine` interface.

### Alternatives Considered

- Let example strategies emit sized trade intents directly.
- Put buying-power logic in the future execution or broker layer only.
- Reject all over-limit intents instead of allowing conservative size reduction.

---

## ADR-016: BacktestBrokerage Owns Simulated Broker State, Not Portfolio Accounting

### Context

Phase 4 adds execution routing and a simulated backtest brokerage, while full
backtest orchestration and internal portfolio accounting are reserved for Phase
5. The project still needs fills and broker-side state in Phase 4 so execution
can be tested realistically.

### Decision

`BacktestBrokerage` implements the normalized `Brokerage` interface and owns
simulated broker-side cash, positions, orders, and fills. It fills accepted
orders only on market events supplied by the caller; it does not load historical
data or run a backtest loop.

The default fill policy remains `next_bar_open`. Initial supported fill policies
are:

- `next_bar_open`
- `next_bar_close`
- `next_bar_typical_price`
- `quote_bid_ask`

Market, limit, stop, and stop-limit orders are simulated with simple
bar/quote/trade trigger rules. Commission and slippage models are intentionally
small and deterministic. Fill slippage is recorded as the per-share price
adjustment applied to the simulated execution price.

### Rationale

This keeps the backtest broker realistic enough for execution tests while
preserving the documented boundary between brokerage state and internal
portfolio accounting. Phase 5 can consume these fills to build ledgers,
snapshots, and reports without changing the broker interface.

### Consequences

- Execution can route approved risk decisions into orders before a full backtest
  engine exists.
- Backtest fill behavior is deterministic and explicitly configured.
- `BacktestBrokerage` can reject orders for insufficient cash or positions.
- Broker-side cash/positions are available for tests and later reconciliation,
  but internal portfolio ledgers remain unimplemented until Phase 5.

### Alternatives Considered

- Put fill simulation directly in the future `BacktestEngine`.
- Defer broker-side cash and position updates until portfolio accounting exists.
- Fill all orders immediately on submission without market events.

---

## ADR-017: Use a Deterministic Bar-Driven Backtest Engine for Phase 5

### Context

Phase 5 is the first end-to-end integration milestone. The system needs to
connect market data, features, strategies, risk, execution, backtest brokerage,
portfolio accounting, and reporting without introducing a broad event framework
too early.

### Decision

Implement `BacktestEngine` as a deterministic bar-driven loop. On each bar, the
engine:

1. advances the data portal,
2. lets `BacktestBrokerage` fill previously submitted orders,
3. applies fills to internal portfolio accounting,
4. marks the portfolio to market,
5. updates features,
6. asks strategies for normalized outputs,
7. evaluates risk,
8. submits approved decisions through execution.

Reports are exported as deterministic Markdown, JSON, and CSV artifacts. Plot
generation remains optional and is not part of the Phase 5 baseline.

### Rationale

This creates a complete, reproducible signal-to-report path while preserving the
existing module boundaries. It is easier to test than a generalized event bus and
still leaves room to evolve the engine later.

### Consequences

- End-to-end backtests can run from a local CSV fixture without third-party
  dependencies.
- Portfolio ledgers and snapshots are generated from fills, not from broker
  state directly.
- Reporting has stable machine-readable artifacts before visual plotting exists.
- More advanced event orchestration can be introduced later if requirements
  justify it.

### Alternatives Considered

- Build a generalized event bus before the first backtest.
- Put portfolio accounting inside `BacktestBrokerage`.
- Delay reporting exports until plotting support exists.

---

## ADR-018: Use a Dependency-Free Alpaca REST Boundary for Phase 6

### Context

Phase 6 adds the first real broker adapter. The local development environment
does not require third-party dependencies, and tests must run without Alpaca
credentials or network access. Alpaca exposes a Trading API v2 with REST
endpoints for orders, account state, open positions, and market clock.

### Decision

Implement a small standard-library REST client under `integrations/alpaca/` and
keep all Alpaca payload mapping at the integration/broker boundary.
`AlpacaBrokerage` consumes that low-level client and implements the existing
normalized `Brokerage` interface.

Phase 6 uses order polling to derive fill deltas from Alpaca order state. A
mock in-memory Alpaca client is provided for dry-run paper engine initialization
and tests. Alpaca market data and streaming order updates remain separate and
are not coupled into the brokerage adapter.

### Rationale

This keeps strategy, risk, execution, and portfolio code unchanged between
backtest and paper modes. It also preserves the project's no-vendor-object
boundary while allowing real paper order submission when credentials are
provided.

### Consequences

- Tests can validate order conversion, errors, polling fills, and paper engine
  wiring without network access.
- Paper trading can initialize safely in mock mode without credentials.
- Fill polling is intentionally conservative and may be replaced or augmented by
  Alpaca trade updates/streams in a later operational-readiness phase.
- Live Alpaca configuration is rejected by the Phase 6 adapter.

### Alternatives Considered

- Require Alpaca's Python SDK as a runtime dependency.
- Pass Alpaca SDK/order objects through execution and portfolio modules.
- Implement streaming updates before the first paper brokerage adapter.

---

## ADR-019: Use a Dependency-Free Directional ML Baseline for Phase 7

### Context

Phase 7 needs to prove the ML workflow boundaries: dataset construction,
labeling, time-aware splitting, leakage checks, training, evaluation, model
registration, runtime inference, and strategy adaptation. The current local
environment can run the project without data-science packages, and the phase
must not depend on external model services or package downloads.

### Decision

Implement Phase 7 with a small dependency-free directional linear baseline and a
filesystem model registry. Offline ML workflow code lives under `qts.ml`.
Runtime trading integration lives in `qts.strategies.ml_strategy` and consumes
registered models through the documented inference interface.

### Rationale

This keeps the project installable and testable in the current environment
while preserving the architecture from ADR-005. The baseline model is enough to
exercise stable workflow contracts without committing the project to a specific
ML framework before the surrounding runtime and monitoring layers exist.

### Consequences

- Phase 7 tests can run without pandas, scikit-learn, model servers, or network
  access.
- Model artifacts are portable JSON files stored by model ID under the local
  registry root.
- More advanced models can be added later behind the same inference and registry
  boundaries.
- Production model monitoring, feature stores, online learning, and
  hyperparameter optimization remain future work.

### Alternatives Considered

- Require scikit-learn or another ML framework immediately.
- Store model artifacts in a database or remote registry.
- Put training code directly inside the strategy layer.

---

## ADR-020: Keep Phase 8 Live Trading Guarded and Dry-Run First

### Context

Phase 8 adds operational readiness features before live trading can be
considered. The project has a paper brokerage adapter, but real live broker
submission still needs stricter operations, credentials, monitoring, and manual
review. The phase requirements prioritize health checks, reconciliation, alerts,
recovery behavior, runbooks, safety gates, and guarded `LiveEngine` scaffolding.

### Decision

Implement `LiveEngine` as a safety-first scaffold. It requires explicit
`LIVE` runtime mode and live safety settings before initialization. Phase 8 only
provides dry-run live brokerage initialization by default; real live broker
submission remains disabled. Order safety validation exists as a reusable guard
for future live submission paths.

### Rationale

This satisfies operational-readiness requirements without crossing into
unguarded live trading. It also keeps broker-specific behavior behind the
normalized brokerage interface and gives future phases a tested safety boundary
for account allowlists, symbol allowlists, max order caps, reconciliation,
alerts, metrics, and recovery behavior.

### Consequences

- Dry-run live initialization is runnable and testable without credentials or
  network access.
- Real live broker submission fails closed until a future phase explicitly
  enables and tests it.
- Future live engines must validate normalized `OrderRequest` objects through
  the same safety helpers before broker submission.
- Operational runbooks are now part of the repository contract.

### Alternatives Considered

- Enable Alpaca live order submission immediately.
- Treat dry-run mode as equivalent to paper trading.
- Put safety checks inside each broker adapter instead of central live
  monitoring/safety helpers.

---

## ADR-021: Add IBKR Through the Existing Brokerage Boundary

### Context

The project needs a second broker target without changing strategy, risk,
execution, or portfolio contracts. Interactive Brokers exposes order, account,
and position operations through Web API style endpoints, and order submission
can return reply prompts that require explicit confirmation.

### Decision

Implement IBKR as a new `IBKRBrokerage` under `brokers/ibkr/` backed by a
dependency-free low-level client and mapping layer under `integrations/ibkr/`.
IBKR uses the same normalized `Brokerage` interface as backtest and Alpaca
paper trading.

IBKR paper order submission requires `broker.account_id` and a
`broker.safety.symbol_conids` mapping from internal symbols to IBKR contract
IDs. Notional-only order requests are rejected by the adapter until explicit
IBKR notional semantics are designed. IBKR order responses requiring manual
reply confirmation fail closed; the adapter does not automatically confirm
those replies.

### Rationale

This preserves the vendor-boundary rule from ADR-006 and the configuration
switching rule from ADR-007. It also makes IBKR testable without credentials or
network access through an in-memory client while avoiding unsafe automatic order
confirmation behavior.

### Consequences

- `PaperTradingEngine` can select either `alpaca_paper` or `ibkr_paper` from
  configuration.
- IBKR market data remains separate future work.
- IBKR live order submission remains disabled by the adapter and by live safety
  gates.
- Users must maintain symbol-to-`conid` mappings in broker safety config or
  attach a `conid`/`ibkr_conid` to individual order request metadata.

### Alternatives Considered

- Add IBKR behavior directly to the paper engine.
- Require the official IBKR SDK or a third-party wrapper immediately.
- Automatically confirm IBKR reply prompts after order submission.

---

## ADR-022: Add Alpaca SIP Data Download Under Market Data

### Context

The project needs a way to fetch historical stock K-line data for research and
backtests. Alpaca provides historical stock bars through the Market Data API,
including SIP feed selection and configurable bar timeframes. The project
already has CSV and Parquet historical providers, so downloaded data can enter
the system through the existing local data path.

### Decision

Implement Alpaca SIP historical data download under `qts.market_data`, not under
broker adapters. Add a config-driven script that requests Alpaca stock bars and
writes normalized CSV or Parquet files compatible with `CSVBarProvider` and
`LocalParquetProvider`.
The template config writes a partitioned dataset by exact downloaded timeframe,
symbol, and date. This keeps multi-symbol and multi-day downloads maintainable
and lets local providers read only files under a dataset root instead of relying
on one large file.
Alpaca requests still use the full configured interval. Intraday rows are then
filtered locally by converting bar timestamps to `America/New_York` and keeping
bar start times in `[09:30, 16:00)`. This makes the session boundary explicit
and avoids depending on subtle upstream API end-boundary behavior.

The supported user-facing K-line levels are:

- `1min`,
- `5min`,
- `15min`,
- `1hour`,
- `1day`.

The current domain model stores broad bar timeframes (`MINUTE`, `HOUR`, `DAY`),
so downloaded output uses the broad domain `timeframe` column and preserves the
exact Alpaca aggregation in `alpaca_timeframe` and `source`.

### Rationale

This keeps market data separate from brokerage per ADR-001 and avoids adding a
new storage backend before it is needed. CSV and Parquet output can be
immediately reused by existing backtest tooling and tests can run without
network access by mocking the HTTP transport.

### Consequences

- Alpaca credentials are reused for data API calls but remain loaded from
  environment variables or `.env`.
- Historical data download is available before live market data streaming.
- Exact sub-hour aggregation is retained in output metadata rather than by
  expanding the stable domain enum.
- Future database export can be added behind the same downloader contract.

### Alternatives Considered

- Put Alpaca data download inside `AlpacaBrokerage`.
- Require Alpaca's Python SDK.
- Change the public `BarTimeframe` enum to add `5Min` and `15Min` immediately.
- Write directly to a database instead of normalized local files.

---

## ADR-023: Treat Runtime Mode, Universe, and Sizing Policy as Explicit Runtime Contracts

### Context

Operational fields such as runtime mode, symbol universe, timeframe, and order
sizing semantics materially affect what the system trades and how broker orders
are formed. Inherited defaults for these fields can hide incomplete runtime
configuration, and notional sizing combined with whole-share execution settings
can create broker-specific ambiguity.

### Decision

Shared base runtime configs may carry safe metadata and path/logging defaults,
but active runtime configs must explicitly declare `runtime.mode`, `symbols`,
and `timeframe`. The config loader fails fast when those fields are missing.

Order sizing also has a deterministic boundary: `TradeIntent` and
`OrderRequest` cannot carry both `quantity` and `notional`, and broker-ready
`OrderRequest` objects must carry exactly one of them. Runtime configs with
`execution.allow_fractional: false` must use quantity-compatible sizing unless
the risk profile is explicitly marked `disabled_until_configured`.

### Rationale

The configuration file is the operator contract for a run. Failing early on
missing active runtime fields and incompatible sizing policies is safer than
allowing defaults to silently select a mode, universe, or broker order semantic.

### Consequences

- Active runtime YAML files are slightly more verbose but self-contained.
- Backtest and Alpaca paper templates use `allow_fractional: true` when they use
  fixed-notional sizing.
- IBKR paper remains quantity-based because the adapter requires quantity order
  payloads.
- Reusable live templates can remain intentionally incomplete only when marked
  `disabled_until_configured`.

### Alternatives Considered

- Keep inherited `BACKTEST` and `[SPY]` defaults in `configs/base.yaml`.
- Convert notional sizing to rounded whole-share quantities automatically.
- Let broker adapters handle ambiguous quantity/notional requests late.

---

## ADR-024: Centralize Exchange Calendar and Session Semantics

### Context

Paper/live health checks, live safety checks, historical data filtering, and
broker fallback market-clock behavior all need consistent answers to basic
session questions. Weekday-only checks are not sufficient for US equities
because they miss holidays, early closes, timezone conversion, regular-session
boundaries, and extended-hours policy.

### Decision

Introduce `qts.calendar` as the canonical owner of exchange calendar and
market-session logic. The first implementation is a deterministic built-in US
equity calendar for `XNYS` and `NASDAQ`, exposed through
`MarketSessionService`.

Runtime configs may define a `market_session` section with exchange, timezone,
regular-session-only versus extended-hours behavior, fail-closed behavior, and
provider selection. Runtime modules should call the shared service rather than
embedding ad hoc weekday/time checks.

### Rationale

Centralizing session semantics keeps backtest, paper, live, market data, and
monitoring behavior aligned. It also lets the system fail closed when a calendar
provider cannot resolve a session, which is safer than silently assuming an
open market.

### Consequences

- Historical Alpaca session filtering now excludes exchange holidays and early
  closes in addition to local clock boundaries.
- Paper/live health and live order safety use the shared session service.
- Broker adapters retain `is_market_open()` for the shared brokerage protocol,
  but fallback behavior now delegates to the default session service instead of
  weekday-only logic.
- Future exchange calendars can be added behind the same provider interface.

### Alternatives Considered

- Keep weekday-only fallback checks.
- Keep historical session filtering as a simple local time comparison.
- Depend immediately on a third-party exchange-calendar package.

---

## ADR-025: Introduce a Deterministic Runtime Event Loop Before Vendor Streams

### Context

Paper and live runtime paths need continuous market-event processing, but
connecting vendor streaming APIs before the event-loop contract is tested would
mix provider concerns with runtime safety rules. The existing paper engine
already exposes `on_market_event()`, so the next safe step is a finite,
deterministic loop that exercises that path without network access.

### Decision

Add `qts.engines.event_loop` with a `MarketEventSource` protocol, an
`InMemoryMarketEventSource` fake stream, and a `RuntimeEventLoop`. The loop
performs duplicate suppression, per-symbol timestamp ordering checks, optional
freshness checks, and `MarketSessionService` filtering before dispatching into
the existing paper engine path.

`PAPER` configs may use `market_data.provider: fake_stream` for local finite
runs. Real vendor websocket adapters remain in the next sub-phase.

### Rationale

This creates a testable runtime boundary first. It keeps Phase B1 deterministic,
network-free, and limited to paper trading while preserving existing strategy,
risk, execution, brokerage, and portfolio interfaces.

### Consequences

- `PaperTradingEngine.start(max_events=...)` can now process finite fake event
  streams.
- Paper configs support both `external_events` and `fake_stream`.
- Live decision-loop dispatch remains deferred until vendor streaming and live
  safety behavior can be designed together.

### Alternatives Considered

- Implement Alpaca/IBKR websocket adapters first.
- Keep the runtime loop entirely inside `PaperTradingEngine`.
- Allow unordered event streams and rely on strategies to detect anomalies.

---

## ADR-026: Keep Vendor Stream Payloads at the Market Data Boundary

### Context

Phase B needs vendor streaming support, but engine code should continue to see
only normalized domain events. Alpaca stream payloads use compact vendor field
names such as `T`, `S`, `bp`, `ap`, `o`, `h`, `l`, `c`, and `v`; allowing those
payloads to leak into paper/live engines would couple runtime orchestration to
one vendor.

### Decision

Add `qts.market_data.streaming` as the owner of Alpaca stream payload
normalization. The first adapter is `AlpacaStreamEventSource`, which consumes an
`AlpacaStreamClient` protocol and yields internal `Bar`/`Quote` models.

The implemented client for this phase is `InMemoryAlpacaStreamClient` so tests
and smoke runs stay deterministic and network-free. Real websocket transport,
heartbeat/reconnect behavior, and guarded live decision dispatch remain in the
next sub-phase.

### Rationale

This preserves the system rule that market data is separate from brokerage and
that engines receive normalized events. It also makes the adapter contract
testable before real streaming transport is introduced.

### Consequences

- Paper runtimes can use `market_data.provider: alpaca_stream` only when mock
  messages or an injected stream client are available.
- Missing real stream transport fails closed with a configuration error.
- Engine code does not parse Alpaca vendor payloads directly.

### Alternatives Considered

- Parse Alpaca payloads inside `PaperTradingEngine`.
- Add a real websocket client immediately.
- Treat Alpaca stream payloads as already-normalized events.

---

## ADR-027: Make Runtime Stream Reliability Policy Explicit and Deterministic

### Context

The runtime event loop needs to handle stream disconnects and stale or gapped
market data in a way that can be tested without real network timing. Real
websocket transports will eventually need backoff, reconnect, and heartbeat
behavior, but adding time sleeps or external connections now would make tests
fragile.

### Decision

Add explicit reconnect and heartbeat policies to `RuntimeEventLoop`.
`RuntimeReconnectPolicy` controls whether a controlled
`StreamDisconnectedError` may reconnect through a source factory, and how many
attempts are allowed. `RuntimeHeartbeatPolicy` treats event timestamp gaps as a
deterministic heartbeat/data-gap proxy and either counts misses or fails closed.

Runtime loop results now expose disconnect, reconnect, heartbeat miss,
source-run, and stopped-reason counters. `market_data.reconnect` and
`market_data.heartbeat` configure these behaviors for paper runtime loops.

### Rationale

This gives the system observable reliability semantics now, while preserving
deterministic, network-free tests. It also creates the policy contract that real
streaming transports can honor later.

### Consequences

- Reconnects require a source factory so new stream resources are explicit.
- Heartbeat checks are based on normalized event timestamps in this phase, not
  wall-clock websocket pings.
- Sleeping backoff is intentionally not implemented yet; `backoff_seconds` is
  validated and reserved for real transports.

### Alternatives Considered

- Add real sleeps and wall-clock timeout behavior to unit tests.
- Retry by reusing the same source object implicitly.
- Treat stream disconnects as ordinary generic data errors.

---

## ADR-028: Live Dry-Run Events Produce Decision Previews, Not Orders

### Context

Live runtime should converge with paper trading by running normalized market
events through feature, strategy, risk, and order-request construction paths.
However, real live order submission remains intentionally disabled until broker
event synchronization and production live safety phases are complete.

### Decision

`LiveEngine.on_market_event()` now supports guarded dry-run decision preview for
bar events. The engine advances live data state, marks the internal portfolio to
market, updates online features, invokes enabled strategies, evaluates risk,
builds a normalized `OrderRequest` preview, and validates live order safety.

The preview is recorded in status output with `would_submit`, preview status,
the serialized order request, and any safety error. The broker adapter is not
called for order submission.

### Rationale

This tests the live decision path without creating an accidental live trading
surface. It keeps the live runtime aligned with paper/backtest contracts while
preserving the fail-closed live safety model.

### Consequences

- Live dry-run bar events can produce safety-approved or safety-rejected
  previews.
- Quote-only events update state but do not trigger bar-based strategy previews.
- Production live submission still requires later broker event stream and live
  enablement phases.

### Alternatives Considered

- Keep live market events as health-only telemetry until production live mode.
- Submit dry-run orders to the live broker adapter.
- Duplicate paper engine order-submission logic inside live mode.

---

## ADR-029: Normalize Broker Lifecycle Updates Before Engine Sync

### Context

Paper broker adapters already expose polling methods for orders and fills, but
the runtime engines handled fills directly and had no stable envelope for future
broker push streams. This made duplicate fill handling and stale order update
behavior easy to implement inconsistently across brokers and engines.

### Decision

Introduce `BrokerEvent` as the normalized broker lifecycle envelope. Broker
events can carry exactly one normalized `Order`, `Fill`, `Account`, or
`Position` payload and are typed by `BrokerEventType`.

Phase C1 uses existing broker polling as the first event source:
`OrderRouter.poll_events()` converts `Brokerage.list_orders(status="all")` and
`Brokerage.poll_fills()` results into broker events. The execution layer applies
these events idempotently, skips duplicate fill IDs, and rejects stale or
regressive order lifecycle updates.

### Rationale

This creates one contract for polling and future push-stream synchronization
without changing broker adapters to expose vendor-specific objects. It also
keeps the current paper runtimes deterministic and network-free while removing
double-application risk from repeated fill polling.

### Consequences

- Paper broker polling now produces normalized broker events before engine
  state changes.
- Future Alpaca/IBKR broker push streams should emit the same `BrokerEvent`
  model instead of adding engine-specific callbacks.
- `BacktestBrokerage.list_orders()` accepts broad `all`, `open`, and `closed`
  filters for polling parity.
- Persistent broker-event checkpoints and vendor push-stream transports remain
  future Phase C work.

### Alternatives Considered

- Keep fill polling as a list of `Fill` objects only.
- Let each engine define its own broker update callback payloads.
- Pass raw Alpaca or IBKR event payloads into runtime engines.

---

## ADR-030: Keep Broker Push Streams Behind Mockable Adapter Boundaries

### Context

After normalized broker events were introduced, the next architectural step was
to prepare for broker push streams without adding network-dependent websocket or
SSE clients. Alpaca and IBKR expose different order/fill update payload shapes,
and those vendor payloads must not leak into engines or execution state.

### Decision

Add vendor-specific broker event adapter boundaries under `integrations/`:

- Alpaca trade updates are consumed through `AlpacaBrokerEventClient` and
  normalized by `AlpacaBrokerEventSource`.
- IBKR order updates are consumed through `IBKRBrokerEventClient` and
  normalized by `IBKRBrokerEventSource`.

The implemented clients are in-memory deterministic clients for tests. The
sources emit normalized `BrokerEvent` order and incremental fill events. Real
network transports, reconnect orchestration, persistent checkpoints, and live
broker submission remain out of scope.

### Rationale

This proves the vendor boundary and keeps test coverage network-free. It also
ensures future real transports will plug into an existing normalized
`BrokerEvent` contract instead of requiring changes to strategy, risk,
execution, or engine code.

### Consequences

- Alpaca and IBKR push-style payloads can be tested locally without credentials.
- Integration modules own vendor payload parsing; engines consume only
  normalized broker events.
- Real broker stream clients must be added behind these protocols in a later
  phase.

### Alternatives Considered

- Add real broker stream transports immediately.
- Parse vendor push payloads inside `PaperTradingEngine` or `LiveEngine`.
- Continue relying only on polling until production live trading.

---

## ADR-031: Checkpoint Broker Event Synchronization Before Production Live Submission

### Context

After broker events and vendor push adapter boundaries were added, engines still
needed a lifecycle synchronization path that could tolerate restarts, duplicate
events, missing-event gaps, and different event delivery ordering. This is
especially important before any future phase enables real live order
submission.

### Decision

Introduce a broker-event synchronization loop in the execution layer:

- `BrokerEventSyncCheckpoint` tracks processed event IDs and the latest event
  timestamp for in-process restart/resume behavior.
- `BrokerEventSyncPolicy` controls duplicate suppression, out-of-order
  fail-closed behavior, and optional timestamp gap checks.
- `BrokerEventSyncResult` reports processed, skipped, duplicate, gap,
  out-of-order, stopped-reason, close, and error counters.
- `PaperTradingEngine.sync_broker_events()` and
  `LiveEngine.sync_broker_events()` consume a `BrokerEventSource` through the
  loop and reconcile broker/portfolio state before and after synchronization.

The checkpoint remains in memory for this phase. Real network transports,
persistent checkpoint storage, and real live order submission remain future
phase work.

### Rationale

The sync loop gives paper and live engines one deterministic lifecycle recovery
contract while preserving the existing vendor-independent `BrokerEvent` model.
It also keeps production live submission blocked until event ordering,
idempotency, and reconciliation behavior are explicit and tested.

### Consequences

- Engine health payloads can expose the latest broker-event synchronization
  result.
- Duplicate broker events are skipped at the sync-loop boundary before reaching
  engine handlers.
- Broker event timestamp gaps can fail closed when configured.
- Execution lifecycle handling must tolerate both fill-first and
  order-update-first delivery without double-counting filled quantity.
- Execution must only mark a broker event processed after successful
  application so recovery can retry failed events.
- Durable restart checkpoints are still required before production live
  trading.

### Alternatives Considered

- Let every engine own its own event checkpoint logic.
- Add persistent checkpoint storage before proving the in-process contract.
- Defer lifecycle hardening until real live submission.

---

## ADR-032: Gate Live Order Submission Behind a Manual Safety Envelope First

### Context

After broker-event synchronization hardening, the next planned work is
production live trading. Enabling automated strategy-driven live submission or
real broker adapters in one step would create too much operational risk. The
system already has guarded dry-run live decision previews, order safety
validation, account allowlists, reconciliation, and normalized brokerage
interfaces.

### Decision

Split Phase D and implement D1 as a manual live order submission envelope:

- Add `broker.safety.enable_order_submission` as a distinct operator gate.
- Add `validate_live_order_submission_config()` to require live mode,
  non-dry-run config, `confirm_live_trading=true`, `broker.paper=false`, a
  `*_live` broker type, and `enable_order_submission=true`.
- Add `LiveEngine.submit_live_order(...)` for manually supplied normalized
  `OrderRequest` objects only.
- Before submission, validate live safety config, account allowlist, order
  request safety, market session, fractional policy, and reconciliation.

Automated conversion of live decision previews into broker submissions and
broker-specific live adapter enablement remain later Phase D sub-phases.

### Rationale

This creates a small, testable production submission surface without changing
strategy behavior or allowing automatic live trading. It also makes the final
operator action explicit: live initialization and live order submission now have
separate gates.

### Consequences

- The default live config remains fail-closed with
  `enable_order_submission=false`.
- Tests can prove submission behavior with injected recording brokerages without
  network access.
- Future broker-specific live adapters can plug into the same `Brokerage`
  interface and D1 submission envelope.
- Automated strategy-driven submission still needs a separate decision,
  kill-switch, monitoring, and lifecycle-sync implementation.

### Alternatives Considered

- Enable real Alpaca live submission immediately.
- Reuse `confirm_live_trading` as the only order-submission gate.
- Automatically submit safety-approved live decision previews.

---

## ADR-033: Enable Alpaca Live Adapter Before Automated Live Submission

### Context

After D1, the system had a manually invoked live order submission path but the
live engine still required an injected brokerage for non-dry-run use. The next
step toward production live trading is to let the engine construct a real
broker-specific live adapter without also enabling automated strategy-driven
submissions.

### Decision

Enable `alpaca_live` as the first selected live brokerage adapter:

- `LiveEngine` constructs `AlpacaBrokerage` only when the runtime is LIVE,
  non-dry-run, `broker.paper=false`, and the D1
  `enable_order_submission=true` gate passes.
- `AlpacaBrokerage` itself rejects unsafe live configurations unless
  `broker_type=alpaca_live`, `paper=false`, `live_enabled=true`,
  `confirm_live_trading=true`, `enable_order_submission=true`, and both
  `dry_run` and `mock_mode` are false.
- Real client construction still requires configured Alpaca credentials and
  uses the live base URL default or `broker.base_url`.
- IBKR live remains fail-closed until a separate phase designs and tests it.

Automated conversion of live decision previews into submitted orders is handled
by ADR-034.

### Rationale

This keeps broker-specific live connectivity behind the same explicit
production gates as manual submission while preserving the normalized
`Brokerage` contract. It also isolates Alpaca-specific behavior in the broker
adapter and avoids expanding the live decision loop before adapter safety is
testable.

### Consequences

- Operators can use the real Alpaca live adapter only after deliberately
  enabling the live confirmation and submission gates.
- Tests can prove adapter construction with injected or patched clients without
  network access.
- The sample live config remains fail-closed by default.
- Automated live strategy submission, live market-data stream ownership, and
  IBKR live behavior remain future work.

### Alternatives Considered

- Continue requiring injected live brokerages for all non-dry-run live runs.
- Enable Alpaca and IBKR live adapters together.
- Couple live adapter enablement to automated strategy submission.

---

## ADR-034: Gate Automated Live Submission Separately From Manual Submission

### Context

D1 introduced a manual `submit_live_order(...)` safety envelope, and D2 allowed
`LiveEngine` to construct the selected Alpaca live adapter behind that envelope.
The remaining production-live step is allowing strategy decisions to submit
orders automatically. That path is riskier than manual submission because it is
triggered by incoming market events, so it needs its own operator gate,
kill-switch, and failure-stop behavior.

### Decision

Automated live decision submission is enabled only when all of these are true:

- D1 live order submission gates pass.
- `broker.safety.enable_automated_submission=true`.
- `broker.safety.automated_submission_kill_switch` is not true.
- The live engine is running.
- The live decision preview is `safety_approved`.
- Reconciliation passes before submission through `submit_live_order(...)`.
- Reconciliation passes again after broker submission.

If broker submission or post-submit reconciliation fails, `LiveEngine` stops
further automated submissions, marks live health critical, records the failure
in health output, and emits a critical alert. Manual submission remains
available through the D1 path if the operator intentionally calls it.

### Rationale

This keeps automated trading opt-in and easy to stop while preserving the
single live submission path. It avoids duplicating order-safety logic inside the
decision loop and gives operators an explicit emergency switch independent of
the broader live-mode and manual-submission gates.

### Consequences

- Default live configs remain non-automated.
- Automated submissions share the same account, symbol, market-session,
  quantity/notional, fractional, and reconciliation checks as manual orders.
- Failures stop future automation without adding real stream ownership or
  restart orchestration.
- Continuous live market-data stream ownership remains future work.

### Alternatives Considered

- Reuse `enable_order_submission` as the only automated gate.
- Let safety-approved previews submit in dry-run mode.
- Continue requiring a manual operator call for all live submissions.

---

## ADR-035: Use Dependency-Free Static SVG Backtest Charts

### Context

Backtest reports already export deterministic Markdown, JSON, and CSV
artifacts. Phase E needs visual diagnostics, but adding a plotting dependency
would increase installation friction for the core standard-library workflow.
The project also does not need an interactive dashboard at this phase.

### Decision

Backtest chart diagnostics are generated as static SVG files using the Python
standard library. Plot export is optional and controlled by
`reporting.generate_plots=true`. The first charts are:

- equity curve with buy/sell fill markers,
- drawdown curve derived from portfolio snapshots.

Plot generation failures are recorded as report warnings and must not prevent
metrics, ledgers, config, equity CSV, or summary artifacts from being written.

### Rationale

SVG keeps reports inspectable in a browser or editor without adding runtime
dependencies. Keeping charts behind configuration preserves the existing
machine-readable reporting baseline and avoids broadening Phase E into a
dashboard project.

### Consequences

- Core report workflows remain dependency-free.
- Chart output is deterministic and easy to test.
- Visual diagnostics are intentionally simple and static.
- More advanced benchmark, factor, or interactive reporting remains future
  work.

### Alternatives Considered

- Add matplotlib or another plotting package as a required dependency.
- Generate HTML dashboards.
- Keep charting entirely outside the project.
