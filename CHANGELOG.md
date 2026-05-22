# CHANGELOG.md

# Changelog

This changelog tracks project changes by phase.

The format follows a simplified Keep a Changelog style.

---

## [Phase 0] - 2026-05-22

### Added

- Created initial documentation package:
  - `SYSTEM_DESIGN.md`
  - `PHASE_PLAN.md`
  - `INTERFACES.md`
  - `DATA_MODELS.md`
  - `DECISIONS.md`
  - `PROJECT_STATE.md`
  - `CHANGELOG.md`
- Defined modular quantitative trading system architecture.
- Defined phase-by-phase implementation plan.
- Defined core interfaces for:
  - market data,
  - features,
  - strategies,
  - ML inference,
  - risk,
  - execution,
  - brokerage,
  - portfolio,
  - engines,
  - reporting.
- Defined stable domain data models.
- Recorded initial architectural decisions.
- Initialized project state and next implementation task.
- Initialized Git repository metadata.
- Added repository scaffold:
  - `pyproject.toml`
  - `README.md`
  - `.env.example`
  - `.gitignore`
  - `configs/base.yaml`
  - `configs/backtest.yaml`
  - `configs/paper_alpaca.yaml`
  - `configs/live_alpaca.yaml`
  - `src/qts/` package layout
  - `tests/test_scaffold.py`
  - `data/.gitkeep`
  - `artifacts/.gitkeep`
- Added placeholder package modules matching the architecture in `SYSTEM_DESIGN.md`.
- Added standard-library smoke tests for required docs, package imports,
  configuration templates, and project metadata.

### Changed

- Updated `PROJECT_STATE.md` to reflect that repository scaffolding exists while
  Phase 1 domain/core implementation remains pending.

### Fixed

- None.

### Removed

- None.

### Notes

- No trading business logic has been implemented.
- No domain models, config loader, clocks, broker adapters, strategies, risk
  rules, execution logic, portfolio accounting, engines, or reporting logic have
  been implemented.
- Phase 1 should start with domain models, core config loading, clocks,
  exceptions, logging, and focused tests.
