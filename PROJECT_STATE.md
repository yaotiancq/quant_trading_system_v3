# PROJECT_STATE.md

# Project State

## 1. Current Status

The project has completed the initial documentation package and repository
scaffold. The Python package layout, basic configuration templates, dependency
metadata, README, and smoke tests exist.

No trading business logic, stable domain models, config loader, clocks,
brokerage behavior, strategy behavior, or backtest engine has been implemented.

- **Current phase:** Phase 1 pending
- **Completed phases:** Phase 0 - Documentation and repository scaffold initialization
- **In-progress phase:** None
- **Next recommended task:** Start Phase 1: Project Skeleton and Core Domain Models

## 2. Completed Phases

| Phase | Status | Notes |
|---|---|---|
| Phase 0 | Complete | Documentation package created. Repository scaffold initialized with package layout, configuration templates, dependency metadata, README, and smoke tests. |

## 3. Pending Phases

| Phase | Status |
|---|---|
| Phase 1: Project Skeleton and Core Domain Models | Pending |
| Phase 2: Market Data and Feature Layer | Pending |
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
- `tests/test_scaffold.py`
- `data/.gitkeep`
- `artifacts/.gitkeep`

Package placeholder modules exist:

- `src/qts/domain/`
- `src/qts/core/`
- `src/qts/market_data/`
- `src/qts/features/`
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

These modules are placeholders only. They intentionally contain no public
business interfaces or runtime behavior yet.

## 5. Missing Modules and Functional Work

Phase 1 still needs to implement:

- domain models and enums from `DATA_MODELS.md`,
- model validation and serialization,
- core config loading and validation,
- `RealClock` and `ReplayClock`,
- common exceptions,
- logging setup,
- unit tests for domain and core behavior.

All later application functionality remains missing:

- real market data loading,
- indicators and feature pipelines,
- strategies,
- risk engine and position sizing,
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

- The current scaffold has no trading functionality by design.
- The existing local virtual environment does not include `pytest`; Phase 0
  smoke tests are runnable with the Python standard library `unittest`.
- Package installation is configured through `pyproject.toml`, but installing
  development extras may require access to package indexes for build/test tools.
- Live trading is intentionally deferred and must remain guarded.
- First implementation target is minute-level bars.
- Second-level data support should be preserved architecturally but not overbuilt early.
- Alpaca is the first real broker target.
- Local Parquet is the first historical data source.
- Backtest brokerage must not own historical data loading.

## 7. Next Recommended Task

Start **Phase 1: Project Skeleton and Core Domain Models**.

The next AI coding agent should:

1. Read:
   - `PROJECT_STATE.md`
   - `PHASE_PLAN.md`
   - `DECISIONS.md`
   - `INTERFACES.md`
   - `DATA_MODELS.md`
   - `CHANGELOG.md`
2. Reuse the existing scaffold rather than recreating it.
3. Implement domain models and enums from `DATA_MODELS.md`.
4. Implement core config loading, clocks, exceptions, and logging setup.
5. Add unit tests for domain models and config validation.
6. Run tests.
7. Update this file and `CHANGELOG.md`.

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
