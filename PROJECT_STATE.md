# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package, repository scaffold,
Phase 1 core foundation, Phase 2 market data/feature layer, Phase 3
strategy/risk layer, Phase 4 execution/backtest brokerage layer, Phase 5
backtest engine/reporting layer, Phase 6 Alpaca paper trading integration,
Phase 7 ML workflow, Phase 8 monitoring/live-trading readiness, and Phase 9
IBKR paper brokerage foundation.

The Python package now includes stable domain enums and data models, core config
loading and validation, clocks, common exceptions, logging setup, local
historical bar providers, data normalization, deterministic replay, a default
data portal, reusable batch indicators, feature schemas, feature pipelines,
broker-agnostic strategy interfaces, SMA crossover and RSI mean-reversion
example strategies, normalized signal-to-intent conversion, position sizing, a
default risk engine, basic risk rules, an execution engine, order request
builder, order manager, order router, fill handler, normalized brokerage
interface, simulated `BacktestBrokerage`, internal portfolio accounting, trade
and cash ledgers, mark-to-market snapshots, a deterministic bar-driven
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

Real live broker order submission remains disabled by default. Phase 8 provides
guarded dry-run initialization and safety validation only.

Post-Phase 8 design review fixes have been applied for replay-bounded backtest
data portal reads, broker/execution dependency direction, and explicit ML
runtime feature schema wiring. ADR-007 follow-up fixes also make the current
paper/live market-data mode explicit through `market_data.provider:
external_events` and enforce `execution.allow_fractional` in runtime order
validation.

- **Current phase:** All documented phases complete
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
- **In-progress phase:** None
- **Next recommended task:** Define the next documented phase or backlog before
  adding functionality beyond Phase 9.

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

## 3. Pending Phases

| Phase | Status |
|---|---|
| None in current `PHASE_PLAN.md` | Complete |

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
- `configs/backtest.yaml`
- `configs/backtest_fixture.yaml`
- `configs/paper_alpaca.yaml`
- `configs/paper_ibkr.yaml`
- `configs/live_alpaca.yaml`
- `configs/ml/directional_baseline.yaml`
- `configs/strategies/ml_directional.yaml`
- `configs/strategies/sma_crossover.yaml`
- `configs/strategies/rsi_mean_reversion.yaml`
- `configs/risk/base.yaml`
- `src/qts/`
- `tests/`
- `docs/runbooks.md`
- `data/.gitkeep`
- `artifacts/.gitkeep`

Domain layer implemented:

- `src/qts/domain/enums.py`
- `src/qts/domain/models.py`
- `src/qts/domain/__init__.py`

Core infrastructure implemented:

- `src/qts/core/config.py`
- `src/qts/core/clocks.py`
- `src/qts/core/exceptions.py`
- `src/qts/core/logging_config.py`
- `src/qts/core/__init__.py`
- `src/qts/cli.py`

Market data layer implemented:

- `src/qts/market_data/interfaces.py`
- `src/qts/market_data/normalization.py`
- `src/qts/market_data/providers.py`
- `src/qts/market_data/portal.py`
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
- `scripts/generate_report.py`
- `scripts/run_paper_trading.py`
- `scripts/train_model.py`
- `scripts/run_live_trading.py`

Tests and fixtures implemented:

- `tests/test_scaffold.py`
- `tests/unit/domain/`
- `tests/unit/core/`
- `tests/unit/market_data/`
- `tests/unit/features/`
- `tests/unit/strategies/`
- `tests/unit/risk/`
- `tests/unit/execution/`
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
  mockable Alpaca and IBKR paper initialization/event-handling paths.
- `PaperTradingEngine` does not yet own a continuous live market-data stream;
  it handles externally supplied `Bar`/`Quote` events and dry-run
  initialization.
- Alpaca market data provider support is not implemented in Phase 6. Paper and
  live scaffolds currently validate `market_data.provider: external_events` and
  consume externally supplied `Bar`/`Quote` events.
- Alpaca and IBKR order/fill updates currently use polling and filled-quantity
  deltas; streaming trade updates remain future operational-readiness work.
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
- Local Parquet is the first historical data source.
- Backtest brokerage must not own historical data loading.
- Buying-power checks use `PortfolioSnapshot.metadata["buying_power"]` when
  present and otherwise fall back to cash.

## 7. Next Recommended Task

Define the next documented phase or backlog item before adding functionality
beyond Phase 9.

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
   readiness layer, and Phase 9 IBKR paper brokerage foundation.
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
