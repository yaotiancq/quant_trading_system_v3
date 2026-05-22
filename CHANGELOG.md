# CHANGELOG.md

# Changelog

This changelog tracks project changes by phase.

The format follows a simplified Keep a Changelog style.

---

## [Phase 1] - 2026-05-22

### Added

- Implemented stable domain enums from `DATA_MODELS.md`.
- Implemented validated dataclass domain models for:
  - market data objects,
  - signals and trade intents,
  - risk decisions,
  - orders and fills,
  - positions, accounts, and portfolio snapshots,
  - ledger entries,
  - backtest results,
  - feature and prediction records,
  - strategy, risk, broker, and runtime config models.
- Added domain serialization helpers that normalize enums and UTC timestamps.
- Implemented core configuration loading and validation:
  - layered YAML config loading with `extends`,
  - deep merge behavior,
  - `.env` key-value loading,
  - validated `RuntimeConfig` construction,
  - optional PyYAML support with a small internal parser for repository templates.
- Implemented `RealClock` and `ReplayClock`.
- Implemented common exception categories.
- Implemented basic logging setup with plain text or JSON formatting.
- Added CLI config validation with `qts --config configs/backtest.yaml`.
- Added Phase 1 unit tests for domain validation, enum values, config loading,
  clocks, and logging.

### Changed

- Updated config templates with valid default symbols, date range, and strategy
  config shape so Phase 1 config loading can validate them.
- Updated `README.md` with Phase 1 status, test commands, and config validation
  instructions.
- Updated `PROJECT_STATE.md` to mark Phase 1 complete and Phase 2 pending.
- Added ADR-013 documenting the standard-library dataclass/config-parser choice.

### Fixed

- None.

### Removed

- None.

### Notes

- Phase 1 does not implement market data providers, indicators, strategies,
  risk rules, execution logic, brokers, portfolio accounting, engines, reporting,
  ML, or live/paper trading runtime behavior.
- Tests run locally with `unittest`; `pytest` remains an optional dependency and
  was not installed in the current virtual environment.

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
