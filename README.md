# Quant Trading System V3

Lightweight modular quantitative trading system foundation.

The architecture documents in the project root are the source of truth:

- `SYSTEM_DESIGN.md`
- `PHASE_PLAN.md`
- `INTERFACES.md`
- `DATA_MODELS.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

## Current Status

Phase 1 is complete. The repository now includes the package layout, validated
domain models and enums, core configuration loading, clocks, common exceptions,
logging setup, configuration templates, and unit tests.

Trading business logic has not been implemented yet. The next milestone is
Phase 2: market data loading and reusable feature/indicator pipelines.

## Layout

```text
configs/          Runtime configuration templates
src/qts/domain/   Stable domain models and enums
src/qts/core/     Config loading, clocks, exceptions, and logging setup
tests/            Smoke and Phase 1 unit tests
data/             Local data placeholder, ignored by git
artifacts/        Runtime output placeholder, ignored by git
```

## Local Setup

Use the existing virtual environment if present, or create one:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

Install the package for development when package build dependencies are
available:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

## Run Tests

The current test suite uses the Python standard library and does not require
pytest:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

If the development extra is installed, pytest can also discover the same tests:

```bash
.venv/bin/python -m pytest
```

## Configuration

Configuration templates live under `configs/`:

- `base.yaml`
- `backtest.yaml`
- `paper_alpaca.yaml`
- `live_alpaca.yaml`

Secrets must not be stored in YAML files. Copy `.env.example` to `.env` for
local secret placeholders when future broker integrations are implemented.

Validate a runtime config through the CLI:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli --config configs/backtest.yaml
```
