# Quant Trading System V3

Lightweight modular quantitative trading system scaffold.

The architecture documents in the project root are the source of truth:

- `SYSTEM_DESIGN.md`
- `PHASE_PLAN.md`
- `INTERFACES.md`
- `DATA_MODELS.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

## Current Status

Phase 0 repository scaffolding is initialized. The package layout, configuration
templates, dependency metadata, and smoke tests exist, but trading business logic
has not been implemented yet.

The next implementation milestone remains Phase 1: stable domain models, core
configuration loading, clocks, exceptions, and logging setup.

## Layout

```text
configs/          Runtime configuration templates
src/qts/          Python package skeleton
tests/            Smoke tests for the scaffold
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

## Run Smoke Tests

The Phase 0 smoke tests use the Python standard library and do not require
pytest:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

If the development extra is installed, pytest can also discover the tests:

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
