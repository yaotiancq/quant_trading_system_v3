# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package, repository scaffold,
Phase 1 core foundation, Phase 2 market data/feature layer, Phase 3
strategy/risk layer, and Phase 4 execution/backtest brokerage layer.

The Python package now includes stable domain enums and data models, core config
loading and validation, clocks, common exceptions, logging setup, local
historical bar providers, data normalization, deterministic replay, a default
data portal, reusable batch indicators, feature schemas, feature pipelines,
broker-agnostic strategy interfaces, SMA crossover and RSI mean-reversion
example strategies, normalized signal-to-intent conversion, position sizing, a
default risk engine, basic risk rules, an execution engine, order request
builder, order manager, order router, fill handler, normalized brokerage
interface, simulated `BacktestBrokerage`, configuration templates, a small CLI
config validation path, and focused unit tests.

No internal portfolio accounting, backtest engine, reporting, ML workflow,
Alpaca brokerage implementation, or live/paper trading runtime has been
implemented.

- **Current phase:** Phase 5 pending
- **Completed phases:**
  - Phase 0 - Documentation and repository scaffold initialization
  - Phase 1 - Project Skeleton and Core Domain Models
  - Phase 2 - Market Data and Feature Layer
  - Phase 3 - Strategy and Risk Layer
  - Phase 4 - Execution Layer and BacktestBrokerage
- **In-progress phase:** None
- **Next recommended task:** Start Phase 5: Backtest Engine and Reporting

## 2. Completed Phases

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | Complete | Documentation package created. Repository scaffold initialized with package layout, configuration templates, dependency metadata, README, and smoke tests. |
| Phase 1 | Complete | Implemented stable domain models/enums, core config loading, clocks, exceptions, logging setup, CLI config validation, and unit tests. |
| Phase 2 | Complete | Implemented local market data interfaces/providers, CSV fixtures, optional Parquet provider, replay, default data portal, batch indicators, feature schema/pipeline, and tests. |
| Phase 3 | Complete | Implemented broker-agnostic strategy interfaces, SMA crossover and RSI example strategies, signal-to-intent conversion, position sizing, basic risk rules, default risk engine, configs, and tests. |
| Phase 4 | Complete | Implemented execution engine, order request builder, order manager, router, fill handler, brokerage protocol, BacktestBrokerage, fill/cost models, broker-side cash/positions, and tests. |

## 3. Pending Phases

| Phase | Status |
|---|---|
| Phase 5: Backtest Engine and Reporting | Pending |
| Phase 6: Alpaca Paper Trading Integration | Pending |
| Phase 7: ML Workflow | Pending |
| Phase 8: Monitoring, Reconciliation, and Live-Trading Readiness | Pending |

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
- `configs/paper_alpaca.yaml`
- `configs/live_alpaca.yaml`
- `configs/strategies/sma_crossover.yaml`
- `configs/strategies/rsi_mean_reversion.yaml`
- `configs/risk/base.yaml`
- `src/qts/`
- `tests/`
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
- `tests/fixtures/market_data/`

Placeholder package modules still exist for later phases:

- `src/qts/ml/`
- `src/qts/brokers/alpaca/`
- `src/qts/integrations/`
- `src/qts/integrations/alpaca/`
- `src/qts/integrations/futu/`
- `src/qts/integrations/polygon/`
- `src/qts/portfolio/`
- `src/qts/engines/`
- `src/qts/reporting/`
- `src/qts/monitoring/`
- `src/qts/research/`
- `src/qts/utils/`

These placeholder modules intentionally contain no Alpaca broker, portfolio,
engine, reporting, monitoring, research, or ML business logic yet.

## 5. Missing Modules and Functional Work

Phase 5 needs to implement:

- backtest engine orchestration,
- internal portfolio accounting,
- trade ledger and cash ledger updates,
- mark-to-market snapshots,
- reporting metrics,
- report artifact export,
- optional plots,
- end-to-end backtest tests.

All later application functionality remains missing:

- Alpaca brokerage implementation,
- paper/live runtime engines,
- reporting,
- monitoring,
- research workflows,
- ML workflows,
- runnable trading scripts.

## 6. Known Issues

- The current foundation has strategy/risk decision behavior and simulated
  execution/backtest brokerage behavior, but no full backtest engine by design.
- `BacktestBrokerage` maintains broker-side cash and positions for simulation;
  internal portfolio accounting, ledgers, and snapshots remain Phase 5 work.
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
- Alpaca is the first real broker target.
- Local Parquet is the first historical data source.
- Backtest brokerage must not own historical data loading.
- Buying-power checks use `PortfolioSnapshot.metadata["buying_power"]` when
  present and otherwise fall back to cash until portfolio/account integration is
  implemented.

## 7. Next Recommended Task

Start **Phase 5: Backtest Engine and Reporting**.

The next AI coding agent should:

1. Read:
   - `PROJECT_STATE.md`
   - `PHASE_PLAN.md`
   - `DECISIONS.md`
   - `INTERFACES.md`
   - `DATA_MODELS.md`
   - `CHANGELOG.md`
2. Reuse the existing Phase 1 domain/core infrastructure, Phase 2
   market-data/feature layer, Phase 3 strategy/risk layer, and Phase 4
   execution/backtest brokerage layer.
3. Implement backtest orchestration, portfolio accounting, and reporting
   behavior according to Phase 5 only.
4. Add focused tests for portfolio accounting, metrics, reporting, and a
   deterministic end-to-end backtest smoke path.
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
