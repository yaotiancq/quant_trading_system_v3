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
