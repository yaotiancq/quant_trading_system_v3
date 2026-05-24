# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package, repository scaffold,
Phase 1 core foundation, Phase 2 market data/feature layer, Phase 3
strategy/risk layer, Phase 4 execution/backtest brokerage layer, Phase 5
backtest engine/reporting layer, Phase 6 Alpaca paper trading integration,
Phase 7 ML workflow, Phase 8 monitoring/live-trading readiness, and Phase 9
IBKR paper brokerage foundation, Phase 10 Alpaca SIP historical data download,
and Major Architecture Phase C1 normalized broker-event polling sync.

The Python package now includes stable domain enums and data models, core config
loading and validation, clocks, common exceptions, logging setup, local
historical bar providers, config-driven Alpaca SIP historical bar download,
data normalization, deterministic replay, a default data portal, reusable batch
indicators, feature schemas, feature pipelines,
broker-agnostic strategy interfaces, SMA crossover and RSI mean-reversion
example strategies, normalized signal-to-intent conversion, position sizing, a
default risk engine, basic risk rules, an execution engine, order request
builder, order manager, order router, fill handler, normalized broker lifecycle
events, normalized brokerage interface, simulated `BacktestBrokerage`, internal
portfolio accounting, trade and cash ledgers, mark-to-market snapshots, a deterministic bar-driven
`BacktestEngine`, reporting metrics, report artifact export, configuration
templates, a small CLI config validation path, runnable backtest scripts, a
dependency-free Alpaca Trading API client boundary, Alpaca payload mapping,
`AlpacaBrokerage`, mock Alpaca client support, portfolio reconciliation,
`PaperTradingEngine`, a paper runtime initialization script, offline ML dataset
construction, forward-return labels, chronological and walk-forward splitting,
leakage checks, a dependency-free directional training pipeline, filesystem
model registry, runtime model inference, an ML strategy adapter, fixture ML
configs, a training script, monitoring health checks, runtime metrics logging,
alert hooks, recovery behavior, broker reconciliation checks, live safety
gates, guarded dry-run `LiveEngine` scaffolding, operational runbooks, and
focused tests. It also includes a dependency-free IBKR Web API client boundary,
IBKR payload mapping, `IBKRBrokerage`, a mock IBKR client, an IBKR paper
configuration template, and mocked IBKR tests.

Post-review config hardening has added reusable strategy `config_ref` imports,
`risk_ref` imports, multiple-base `extends`, circular include detection, strict
runtime config validation, deterministic path resolution, effective-config CLI
inspection commands, exact `bar_interval` filtering, and data-adjustment
validation for local historical bars.

The latest post-review correctness pass removes inherited active runtime
defaults from the shared base config, preserves full referenced-profile
provenance, propagates configured timeframes into local CSV/Parquet providers,
enforces quantity/notional exclusivity, validates fixed-notional sizing against
the fractional execution policy, tightens session/cooldown/daily-loss risk
rules, rejects mismatched injected strategy lists, supports explicit reporting
annualization settings, and fixes the IBKR fill polling `since` boundary.

Major Architecture Phase A has added a shared exchange calendar and
market-session service under `qts.calendar`. Runtime configs now support
`market_session`, Alpaca historical session filtering uses the shared US equity
calendar, paper/live health checks and live order safety use the shared service,
and broker fallback `is_market_open()` implementations no longer use
weekday-only logic.

Major Architecture Phase B1 has added a deterministic runtime market-event loop
foundation. Paper configs can now use `market_data.provider: fake_stream`,
finite fake streams can drive `PaperTradingEngine.start(max_events=...)`, and
the loop applies duplicate suppression, out-of-order fail-closed checks,
optional freshness checks, and `MarketSessionService` filtering before dispatch.

Major Architecture Phase B2a has added a mockable Alpaca stream adapter
boundary. Paper configs can now use `market_data.provider: alpaca_stream` with
Alpaca-shaped `mock_messages` or an injected stream client; the adapter
normalizes Alpaca bar/quote payloads into internal `Bar`/`Quote` events before
they enter the runtime event loop.

Major Architecture Phase B2b1 has added bounded reconnect and heartbeat/data-gap
policy to the runtime market-event loop. Event-loop health output now includes
disconnect, reconnect, heartbeat miss, source-run, and stopped-reason counters,
and paper runtime loops read `market_data.reconnect` and
`market_data.heartbeat` settings.

Major Architecture Phase B2b2 has added guarded live decision preview. Dry-run
live bar events now run through live data portal state, feature updates,
strategies, risk evaluation, normalized order-request construction, and live
safety validation, then record a preview without calling broker order
submission.

Major Architecture Phase C1 has added normalized broker events and polling
synchronization. Broker order/fill/account/position updates now have a stable
`BrokerEvent` envelope, existing broker polling can emit order/fill events, the
execution layer applies broker events idempotently, and the paper engine routes
polling fallback through that event contract.

Real live broker order submission remains disabled by default. Phase 8 provides
guarded dry-run initialization and safety validation only.

Post-Phase 8 design review fixes have been applied for replay-bounded backtest
data portal reads, broker/execution dependency direction, and explicit ML
runtime feature schema wiring. ADR-007 follow-up fixes made the original
paper/live market-data mode explicit through `market_data.provider:
external_events`; Phase B1 adds paper-only `fake_stream` support, and Phase B2a
adds paper-only `alpaca_stream` adapter support. Phase B2b1 adds runtime stream
reliability policy. Phase B2b2 adds guarded dry-run live decision previews.
Phase C1 adds normalized broker-event polling synchronization. Live remains
external-event driven and real live broker submission remains disabled. Runtime
order validation also enforces `execution.allow_fractional`.

- **Current phase:** Major Architecture Phase C1 complete
- **Completed phases:**
  - Phase 0 - Documentation and repository scaffold initialization
  - Phase 1 - Project Skeleton and Core Domain Models
  - Phase 2 - Market Data and Feature Layer
  - Phase 3 - Strategy and Risk Layer
  - Phase 4 - Execution Layer and BacktestBrokerage
  - Phase 5 - Backtest Engine and Reporting
  - Phase 6 - Alpaca Paper Trading Integration
  - Phase 7 - ML Workflow
  - Phase 8 - Monitoring, Reconciliation, and Live-Trading Readiness
  - Phase 9 - IBKR Paper Brokerage Foundation
  - Phase 10 - Alpaca SIP Historical Data Download
  - Major Architecture Phase A - Exchange Calendar and Market Session Service
  - Major Architecture Phase B1 - Deterministic Runtime Event Loop and Fake Stream
  - Major Architecture Phase B2a - Alpaca Stream Adapter Boundary for Paper Runtime
  - Major Architecture Phase B2b1 - Runtime Reconnect and Heartbeat Policy
  - Major Architecture Phase B2b2 - Guarded Live Decision Preview
  - Major Architecture Phase C1 - Normalized Broker Events and Polling Sync
- **In-progress phase:** None
- **Next recommended task:** Major Architecture Phase C2 - Vendor Broker Push
  Adapter Boundaries.

## 2. Completed Phases

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | Complete | Documentation package created. Repository scaffold initialized with package layout, configuration templates, dependency metadata, README, and smoke tests. |
| Phase 1 | Complete | Implemented stable domain models/enums, core config loading, clocks, exceptions, logging setup, CLI config validation, and unit tests. |
| Phase 2 | Complete | Implemented local market data interfaces/providers, CSV fixtures, optional Parquet provider, replay, default data portal, batch indicators, feature schema/pipeline, and tests. |
| Phase 3 | Complete | Implemented broker-agnostic strategy interfaces, SMA crossover and RSI example strategies, signal-to-intent conversion, position sizing, basic risk rules, default risk engine, configs, and tests. |
| Phase 4 | Complete | Implemented execution engine, order request builder, order manager, router, fill handler, brokerage protocol, BacktestBrokerage, fill/cost models, broker-side cash/positions, and tests. |
| Phase 5 | Complete | Implemented internal portfolio accounting, ledgers, mark-to-market snapshots, bar-driven BacktestEngine, metrics, report artifact export, fixture backtest config, scripts, and tests. |
| Phase 6 | Complete | Implemented Alpaca integration client/mapping, AlpacaBrokerage, mock paper mode, paper engine initialization/event handling, portfolio reconciliation, runner script, and mocked tests. |
| Phase 7 | Complete | Implemented ML dataset building, forward-return labeling, time-aware splits, leakage checks, dependency-free directional model training/evaluation, filesystem registry, runtime inference, ML signal strategy adapter, fixture configs, training script, and tests. |
| Phase 8 | Complete | Implemented monitoring health checks, metrics, alerts, recovery behavior, broker reconciliation checks, live safety gates, guarded dry-run LiveEngine scaffolding, live runner script, runbooks, and tests. |
| Phase 9 | Complete | Implemented dependency-free IBKR client/mapping, IBKRBrokerage, mock paper mode, IBKR paper config, paper engine factory support, and mocked tests. |
| Phase 10 | Complete | Implemented config-driven Alpaca SIP historical bar downloader, partitioned CSV/Parquet output, download script, data config template, docs, and tests. |
| Major Architecture Phase A | Complete | Implemented shared US equity calendar/session service, runtime config validation, Alpaca filtering integration, paper/live health checks, live order safety, and tests. |
| Major Architecture Phase B1 | Complete | Implemented deterministic runtime event-loop primitives, fake in-memory stream support, paper-engine finite stream execution, config template, and tests. |
| Major Architecture Phase B2a | Complete | Implemented mockable Alpaca stream payload adapter, paper-engine stream source wiring, config template, and tests. |
| Major Architecture Phase B2b1 | Complete | Implemented runtime reconnect/heartbeat policy, event-loop health counters, config validation, and tests. |
| Major Architecture Phase B2b2 | Complete | Implemented guarded live dry-run decision previews through feature, strategy, risk, order-request, and live safety validation without broker submission. |
| Major Architecture Phase C1 | Complete | Implemented normalized broker events, polling fallback event conversion, idempotent execution lifecycle updates, and paper-engine broker polling sync. |

## 3. Pending Phases

| Phase | Status |
|---|---|
| Major Architecture Phase C2 - Vendor Broker Push Adapter Boundaries | Planned |
| Major Architecture Phase C3 - Engine Lifecycle Synchronization Hardening | Planned |
| Major Architecture Phase D - Production Live-Trading Enablement | Blocked until A-C complete |
| Major Architecture Phase E - Chart Reporting and Visual Backtest Diagnostics | Planned |
| Major Architecture Phase F - Production ML Contracts and Model Governance | Planned |

## 4. Implemented Modules

Documentation exists:

- `SYSTEM_DESIGN.md`
- `PHASE_PLAN.md`
- `INTERFACES.md`
- `DATA_MODELS.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

Repository scaffold exists:

- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `configs/base.yaml`
- `configs/data/alpaca_sip_bars.yaml`
- `configs/backtest.yaml`
- `configs/backtest_fixture.yaml`
- `configs/paper_alpaca.yaml`
- `configs/paper_ibkr.yaml`
- `configs/paper_fake_stream.yaml`
- `configs/paper_alpaca_stream_mock.yaml`
- `configs/live_alpaca.yaml`
- `configs/ml/directional_baseline.yaml`
- `configs/strategies/ml_directional.yaml`
- `configs/strategies/sma_crossover.yaml`
- `configs/strategies/rsi_mean_reversion.yaml`
- `configs/risk/base.yaml`
- `src/qts/`
- `tests/`
- `docs/runbooks.md`
- `docs/user_manual.md`
- `docs/system_handbook.md`
- `data/.gitkeep`
- `artifacts/.gitkeep`

Domain layer implemented:

- `src/qts/domain/enums.py`
- `src/qts/domain/models.py`
- `src/qts/domain/__init__.py`

Core infrastructure implemented:

- `src/qts/calendar/`
- `src/qts/core/config.py`
- `src/qts/core/clocks.py`
- `src/qts/core/exceptions.py`
- `src/qts/core/logging_config.py`
- `src/qts/core/__init__.py`
- `src/qts/cli.py`

Market data layer implemented:

- `src/qts/market_data/interfaces.py`
- `src/qts/market_data/alpaca.py`
- `src/qts/market_data/normalization.py`
- `src/qts/market_data/providers.py`
- `src/qts/market_data/portal.py`
- `src/qts/market_data/streaming.py`
- `src/qts/market_data/__init__.py`

Feature layer implemented:

- `src/qts/features/indicators.py`
- `src/qts/features/pipeline.py`
- `src/qts/features/__init__.py`

Strategy layer implemented:

- `src/qts/strategies/base.py`
- `src/qts/strategies/rule_based.py`
- `src/qts/strategies/ml_strategy.py`
- `src/qts/strategies/__init__.py`

Risk layer implemented:

- `src/qts/risk/types.py`
- `src/qts/risk/sizing.py`
- `src/qts/risk/rules.py`
- `src/qts/risk/engine.py`
- `src/qts/risk/__init__.py`

Execution layer implemented:

- `src/qts/execution/events.py`
- `src/qts/execution/orders.py`
- `src/qts/execution/manager.py`
- `src/qts/execution/fills.py`
- `src/qts/execution/router.py`
- `src/qts/execution/engine.py`
- `src/qts/execution/__init__.py`

Brokerage layer implemented:

- `src/qts/brokers/interfaces.py`
- `src/qts/brokers/__init__.py`
- `src/qts/brokers/backtest/brokerage.py`
- `src/qts/brokers/backtest/__init__.py`
- `src/qts/brokers/alpaca/brokerage.py`
- `src/qts/brokers/alpaca/__init__.py`
- `src/qts/brokers/ibkr/brokerage.py`
- `src/qts/brokers/ibkr/__init__.py`

Integration layer implemented:

- `src/qts/integrations/alpaca/client.py`
- `src/qts/integrations/alpaca/mapping.py`
- `src/qts/integrations/alpaca/mock.py`
- `src/qts/integrations/alpaca/__init__.py`
- `src/qts/integrations/ibkr/client.py`
- `src/qts/integrations/ibkr/mapping.py`
- `src/qts/integrations/ibkr/mock.py`
- `src/qts/integrations/ibkr/__init__.py`

Portfolio layer implemented:

- `src/qts/portfolio/accounting.py`
- `src/qts/portfolio/__init__.py`

Runtime engines implemented:

- `src/qts/engines/backtest_engine.py`
- `src/qts/engines/event_loop.py`
- `src/qts/engines/market_data.py`
- `src/qts/engines/paper_trading_engine.py`
- `src/qts/engines/live_engine.py`
- `src/qts/engines/__init__.py`

Reporting layer implemented:

- `src/qts/reporting/metrics.py`
- `src/qts/reporting/reporter.py`
- `src/qts/reporting/__init__.py`

ML workflow layer implemented:

- `src/qts/ml/types.py`
- `src/qts/ml/labels.py`
- `src/qts/ml/dataset.py`
- `src/qts/ml/splits.py`
- `src/qts/ml/leakage.py`
- `src/qts/ml/models.py`
- `src/qts/ml/registry.py`
- `src/qts/ml/inference.py`
- `src/qts/ml/training.py`
- `src/qts/ml/__init__.py`

Monitoring and live-readiness layer implemented:

- `src/qts/monitoring/types.py`
- `src/qts/monitoring/health.py`
- `src/qts/monitoring/metrics.py`
- `src/qts/monitoring/alerts.py`
- `src/qts/monitoring/safety.py`
- `src/qts/monitoring/reconciliation.py`
- `src/qts/monitoring/recovery.py`
- `src/qts/monitoring/__init__.py`

Scripts implemented:

- `scripts/run_backtest.py`
- `scripts/download_data.py`
- `scripts/generate_report.py`
- `scripts/run_paper_trading.py`
- `scripts/train_model.py`
- `scripts/run_live_trading.py`

Tests and fixtures implemented:

- `tests/test_scaffold.py`
- `tests/unit/domain/`
- `tests/unit/calendar/`
- `tests/unit/core/`
- `tests/unit/market_data/`
- `tests/unit/features/`
- `tests/unit/strategies/`
- `tests/unit/risk/`
- `tests/unit/execution/`
- `tests/unit/engines/`
- `tests/unit/brokers/backtest/`
- `tests/unit/brokers/alpaca/`
- `tests/unit/brokers/ibkr/`
- `tests/unit/integrations/alpaca/`
- `tests/unit/integrations/ibkr/`
- `tests/unit/portfolio/`
- `tests/unit/reporting/`
- `tests/unit/ml/`
- `tests/unit/monitoring/`
- `tests/integration/backtest/`
- `tests/integration/alpaca/`
- `tests/integration/ibkr/`
- `tests/integration/ml/`
- `tests/integration/live_safety/`
- `tests/fixtures/market_data/`
- `tests/fixtures/market_data/backtest_sma_cross.csv`
- `tests/fixtures/market_data/ml_directional.csv`

Placeholder package modules still exist for later phases:

- `src/qts/integrations/`
- `src/qts/integrations/futu/`
- `src/qts/integrations/polygon/`
- `src/qts/research/`
- `src/qts/utils/`

These placeholder modules intentionally contain no research, Futu, or Polygon
vendor business logic yet.

## 5. Missing Modules and Functional Work

Future functionality outside the current phase plan remains missing:

- research workflows,
- production deployment automation,
- real live broker order submission,
- production dashboarding and notification integrations.

## 6. Known Issues

- The current foundation has a deterministic bar-driven backtest path and
  mockable Alpaca and IBKR paper initialization/event-handling paths, plus a
  finite fake-stream paper event loop and mock Alpaca stream adapter path for
  deterministic local testing.
- `PaperTradingEngine` does not yet own a vendor-backed continuous live
  market-data stream; it handles externally supplied `Bar`/`Quote` events,
  finite fake streams, mock Alpaca stream payloads, and dry-run initialization.
- The runtime event loop has deterministic reconnect and heartbeat/data-gap
  policies, but no real websocket transport or sleeping backoff implementation.
- Live Alpaca market data provider support is not implemented. Phase 10 adds
  historical SIP downloads only; live scaffolds still validate
  `market_data.provider: external_events`, while paper also supports
  `fake_stream` and `alpaca_stream` for finite local runs.
- Alpaca and IBKR order/fill synchronization currently uses normalized broker
  events built from polling and filled-quantity deltas; vendor push-stream
  trade updates remain future operational-readiness work.
- IBKR paper order submission requires `broker.account_id` and
  `broker.safety.symbol_conids`; automatic IBKR order reply confirmation is not
  enabled and reply prompts fail closed.
- Phase 8 live readiness is dry-run and safety-gated only. Real live broker
  order submission remains disabled and should require a new documented phase.
- The Phase 7 ML model is a dependency-free directional baseline intended to
  validate workflow boundaries. Advanced model libraries, feature stores,
  online learning, optimization, and production model monitoring remain future
  work.
- Plot generation is not implemented; Phase 5 exports Markdown, JSON, and CSV
  report artifacts.
- `pytest` is listed as an optional test dependency but is not installed in the
  current local virtual environment. The test suite currently runs with
  standard-library `unittest`.
- Config loading supports PyYAML if installed and otherwise uses an internal
  parser for the repository's simple YAML templates. This parser is intentionally
  limited.
- Parquet loading is implemented through optional pandas or pyarrow dependencies.
  CSV fixtures remain the guaranteed no-dependency test path.
- Live trading is intentionally deferred and must remain guarded.
- First implementation target is minute-level bars.
- Second-level data support should be preserved architecturally but not overbuilt early.
- Alpaca is the first real broker target and now has a paper adapter.
- IBKR is the second broker target and now has a paper adapter foundation.
- Alpaca SIP is the first remote historical data download target and writes
  normalized CSV or Parquet for the existing local provider/backtest path. The
  sample config now writes a partitioned dataset by timeframe, symbol, and date
  so multi-symbol downloads do not accumulate in one large file. Intraday rows
  are locally filtered to regular US equity session start times after requesting
  the full configured Alpaca interval.
- Local Parquet is the first historical data source.
- Backtest brokerage must not own historical data loading.
- Buying-power checks use `PortfolioSnapshot.metadata["buying_power"]` when
  present and otherwise fall back to cash.

## 7. Next Recommended Task

Define the next documented phase or backlog item before adding functionality
beyond Phase 10.

The next AI coding agent should:

1. Read:
   - `PROJECT_STATE.md`
   - `PHASE_PLAN.md`
   - `DECISIONS.md`
   - `INTERFACES.md`
   - `DATA_MODELS.md`
   - `CHANGELOG.md`
2. Reuse the existing Phase 1 domain/core infrastructure, Phase 2
   market-data/feature layer, Phase 3 strategy/risk layer, Phase 4
   execution/brokerage layer, Phase 5 backtest/reporting layer, Phase 6
   Alpaca paper integration, Phase 7 ML workflow, Phase 8 monitoring/live
   readiness layer, Phase 9 IBKR paper brokerage foundation, and Phase 10
   Alpaca SIP historical data download.
3. Check whether `PHASE_PLAN.md` has been extended with a new phase. If not,
   update the planning documents before implementing new functional scope.
4. Preserve the Phase 8 live-safety guardrails unless a future phase explicitly
   changes them and documents the reason.
5. Run tests.
6. Update this file and `CHANGELOG.md`.

## 8. Rules for Future AI Coding Agent Sessions

Every new session must:

- inspect the existing repository before editing,
- continue from the next unfinished task,
- not restart the project from scratch,
- keep phase boundaries clear,
- avoid implementing future-phase functionality unless required for current-phase testability,
- prefer minimal complete functionality over broad incomplete implementation,
- write tests for the phase being implemented,
- update documentation after each phase.

## 9. Required Updates After Every Phase

At the end of each phase, update:

- `PROJECT_STATE.md`
  - current phase,
  - completed phases,
  - implemented modules,
  - missing modules,
  - known issues,
  - next recommended task.
- `CHANGELOG.md`
  - added,
  - changed,
  - fixed,
  - removed,
  - notes.

Also update when relevant:

- `DECISIONS.md` for new architectural decisions.
- `INTERFACES.md` for public interface changes.
- `DATA_MODELS.md` for stable model changes.
- `PHASE_PLAN.md` if phase scope changes.
