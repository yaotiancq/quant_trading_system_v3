# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package, repository scaffold,
Phase 1 core foundation, and Phase 2 market data/feature layer.

The Python package now includes stable domain enums and data models, core config
loading and validation, clocks, common exceptions, logging setup, local
historical bar providers, data normalization, deterministic replay, a default
data portal, reusable batch indicators, feature schemas, feature pipelines,
configuration templates, a small CLI config validation path, and focused unit
tests.

No strategies, risk engine, execution layer, brokerage implementation, portfolio
accounting, backtest engine, reporting, ML workflow, or live/paper trading
runtime has been implemented.

- **Current phase:** Phase 3 pending
- **Completed phases:**
  - Phase 0 - Documentation and repository scaffold initialization
  - Phase 1 - Project Skeleton and Core Domain Models
  - Phase 2 - Market Data and Feature Layer
- **In-progress phase:** None
- **Next recommended task:** Start Phase 3: Strategy and Risk Layer

## 2. Completed Phases

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | Complete | Documentation package created. Repository scaffold initialized with package layout, configuration templates, dependency metadata, README, and smoke tests. |
| Phase 1 | Complete | Implemented stable domain models/enums, core config loading, clocks, exceptions, logging setup, CLI config validation, and unit tests. |
| Phase 2 | Complete | Implemented local market data interfaces/providers, CSV fixtures, optional Parquet provider, replay, default data portal, batch indicators, feature schema/pipeline, and tests. |

## 3. Pending Phases

| Phase | Status |
|---|---|
| Phase 3: Strategy and Risk Layer | Pending |
| Phase 4: Execution Layer and BacktestBrokerage | Pending |
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

Tests and fixtures implemented:

- `tests/test_scaffold.py`
- `tests/unit/domain/`
- `tests/unit/core/`
- `tests/unit/market_data/`
- `tests/unit/features/`
- `tests/fixtures/market_data/`

Placeholder package modules still exist for later phases:

- `src/qts/strategies/`
- `src/qts/ml/`
- `src/qts/risk/`
- `src/qts/execution/`
- `src/qts/brokers/`
- `src/qts/brokers/backtest/`
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

These placeholder modules intentionally contain no strategy, risk, execution,
broker, portfolio, engine, reporting, monitoring, research, or ML business logic yet.

## 5. Missing Modules and Functional Work

Phase 3 needs to implement:

- base `Strategy` interface,
- example SMA crossover strategy,
- example RSI mean reversion strategy,
- normalized signal/trade-intent generation,
- risk rule and risk engine interfaces,
- position sizing,
- basic risk rules,
- risk decision reasons,
- focused tests and configs for strategy and risk behavior.

All later application functionality remains missing:

- execution layer,
- brokerage implementations,
- portfolio accounting,
- runtime engines,
- reporting,
- monitoring,
- research workflows,
- ML workflows,
- runnable trading scripts.

## 6. Known Issues

- The current foundation has no trading decision or order execution behavior by design.
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

## 7. Next Recommended Task

Start **Phase 3: Strategy and Risk Layer**.

The next AI coding agent should:

1. Read:
   - `PROJECT_STATE.md`
   - `PHASE_PLAN.md`
   - `DECISIONS.md`
   - `INTERFACES.md`
   - `DATA_MODELS.md`
   - `CHANGELOG.md`
2. Reuse the existing Phase 1 domain/core infrastructure and Phase 2
   market-data/feature layer.
3. Implement strategy and risk behavior according to Phase 3 only.
4. Add focused tests for strategies, risk rules, and position sizing.
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
