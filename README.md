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

Phase 5 is complete. The repository now includes the package layout, validated
domain models and enums, core configuration loading, clocks, common exceptions,
logging setup, local market data providers, deterministic replay, reusable batch
indicators, feature schemas, feature pipelines, broker-agnostic example
strategies, a risk engine with position sizing and basic rules, an execution
engine, order manager/router, normalized brokerage protocol, simulated
BacktestBrokerage, internal portfolio accounting, a deterministic backtest
engine, reporting metrics and artifacts, configuration templates, and tests.

Real broker adapters, paper/live trading runtime, ML workflows, and operational
monitoring are intentionally deferred. The next milestone is Phase 6: Alpaca
paper trading integration.

## Layout

```text
configs/          Runtime configuration templates
src/qts/domain/   Stable domain models and enums
src/qts/core/     Config loading, clocks, exceptions, and logging setup
src/qts/market_data/
                  Local historical data loading, normalization, replay, portal
src/qts/features/ Reusable batch indicators and feature pipelines
src/qts/strategies/
                  Strategy interface, SMA crossover, RSI mean reversion
src/qts/risk/     Position sizing, risk rules, and risk engine
src/qts/execution/
                  Order requests, manager, router, fill handler, engine
src/qts/brokers/  Brokerage protocol and BacktestBrokerage simulation
src/qts/portfolio/
                  Portfolio accounting, cash ledger, trade ledger, snapshots
src/qts/engines/  Deterministic BacktestEngine
src/qts/reporting/
                  Backtest metrics and report artifact export
scripts/          Local backtest and report commands
tests/            Smoke, unit, and integration tests through Phase 5
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

For Parquet-backed historical data, install the optional data extra when package
indexes are available:

```bash
.venv/bin/python -m pip install -e ".[data]"
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
- `backtest_fixture.yaml`
- `paper_alpaca.yaml`
- `live_alpaca.yaml`
- `strategies/sma_crossover.yaml`
- `strategies/rsi_mean_reversion.yaml`
- `risk/base.yaml`

Secrets must not be stored in YAML files. Copy `.env.example` to `.env` for
local secret placeholders when future broker integrations are implemented.

Validate a runtime config through the CLI:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli --config configs/backtest.yaml
```

The Phase 2 CSV fixture provider can be exercised from Python:

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from qts.market_data import CSVBarProvider

provider = CSVBarProvider("tests/fixtures/market_data/bars.csv")
bars = provider.get_history(["SPY"], "2024-01-02T14:30:00Z", "2024-01-02T14:35:00Z", "MINUTE")
print(len(bars), bars[-1].symbol, bars[-1].close)
PY
```

Phase 3 strategy and risk components are importable from `qts.strategies` and
`qts.risk`. They generate and approve/reject normalized domain objects only;
Phase 4 execution converts approved decisions into order requests.

Phase 4 execution and backtest brokerage components are importable from
`qts.execution` and `qts.brokers.backtest`. `BacktestBrokerage` fills orders only
from market events supplied by the caller; `qts.engines.BacktestEngine` supplies
the Phase 5 backtest loop.

Run the Phase 5 fixture backtest:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_backtest.py --config configs/backtest_fixture.yaml
```

Generate report artifacts:

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_report.py --config configs/backtest_fixture.yaml
```
