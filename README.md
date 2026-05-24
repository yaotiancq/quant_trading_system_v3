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

Phase 10 is complete. The repository now includes the package layout, validated
domain models and enums, core configuration loading, clocks, common exceptions,
logging setup, local market data providers, a config-driven Alpaca SIP
historical bar downloader, a shared US equity calendar/session service,
deterministic replay, reusable batch indicators,
feature schemas, feature pipelines, broker-agnostic example strategies, a risk
engine with position sizing and basic rules, an execution engine, order
manager/router, normalized brokerage protocol, simulated BacktestBrokerage,
internal portfolio accounting, a deterministic backtest engine, reporting
metrics and artifacts, a dependency-free Alpaca paper brokerage adapter, a paper
trading engine initialization path, configuration templates, an offline ML
workflow, a filesystem model registry, runtime ML inference, an ML signal
strategy adapter, monitoring and alert helpers, reconciliation health checks,
guarded live safety gates, dry-run `LiveEngine` scaffolding, a dependency-free
IBKR paper brokerage foundation, operational runbooks, and tests.

Real live broker order submission remains disabled by default. The documented
phase plan is complete through Phase 10; future work should be captured in a new
phase or backlog before implementation.

## Layout

```text
configs/          Runtime configuration templates
src/qts/domain/   Stable domain models and enums
src/qts/core/     Config loading, clocks, exceptions, and logging setup
src/qts/calendar/ Exchange calendar and market-session service
src/qts/market_data/
                  Local data loading, Alpaca SIP downloads, normalization, replay, portal
src/qts/features/ Reusable batch indicators and feature pipelines
src/qts/strategies/
                  Strategy interface, SMA crossover, RSI mean reversion
src/qts/risk/     Position sizing, risk rules, and risk engine
src/qts/execution/
                  Order requests, manager, router, fill handler, engine
src/qts/brokers/  Brokerage protocol, BacktestBrokerage, AlpacaBrokerage, IBKRBrokerage
src/qts/integrations/
                  Low-level vendor clients and mapping adapters
src/qts/portfolio/
                  Portfolio accounting, ledgers, snapshots, reconciliation
src/qts/engines/  BacktestEngine, PaperTradingEngine, and runtime event loop
src/qts/reporting/
                  Backtest metrics and report artifact export
src/qts/ml/       Offline datasets, labels, splits, training, registry, inference
src/qts/monitoring/
                  Health checks, metrics, alerts, recovery, safety gates
scripts/          Local data download, backtest, report, paper, ML, and live dry-run commands
docs/             User manual, system handbook, and operational runbooks
tests/            Smoke, unit, and integration tests through Phase 10
data/             Local data placeholder, ignored by git
artifacts/        Runtime output placeholder, ignored by git
```

## Documentation

- `docs/user_manual.md` is the detailed operator manual for setup, configs,
  test commands, backtests, reports, paper brokers, ML training, live dry-run,
  and troubleshooting.
- `docs/system_handbook.md` is the engineering handbook: architecture map,
  runtime flows, file-by-file reference, and guidance for extending the system.
- `docs/runbooks.md` contains operational procedures for live-readiness and
  incident-style workflows.

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
- `data/alpaca_sip_bars.yaml`
- `paper_alpaca.yaml`
- `paper_fake_stream.yaml`
- `paper_alpaca_stream_mock.yaml`
- `live_alpaca.yaml`
- `paper_ibkr.yaml`
- `ml/directional_baseline.yaml`
- `strategies/sma_crossover.yaml`
- `strategies/rsi_mean_reversion.yaml`
- `strategies/ml_directional.yaml`
- `risk/base.yaml`

Secrets must not be stored in YAML files. Copy `.env.example` to `.env` for
local Alpaca paper credentials or IBKR Web API overrides when using real broker
APIs.

Active runtime configs must explicitly set `runtime.mode`, `symbols`, and
`timeframe`; `configs/base.yaml` only carries safe shared metadata/defaults.
If `execution.allow_fractional: false`, use quantity-based risk sizing so
broker-ready orders do not carry notional-only sizing.
Runtime configs may also set `market_session` to control exchange session
behavior. The built-in provider currently supports US equities for `XNYS` and
`NASDAQ`, regular-session-only or extended-hours checks, and fail-closed
behavior when a session cannot be resolved.

Paper templates can use `market_data.provider: external_events` when another
process supplies `Bar`/`Quote` events, `fake_stream` for deterministic finite
local runs, or `alpaca_stream` for Alpaca-shaped mock stream payloads. Live
templates still use `external_events`. Alpaca historical SIP downloads are
available through `scripts/download_data.py`; real websocket stream transport
remains future work.

Validate a runtime config through the CLI:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli --config configs/backtest.yaml
```

Inspect the resolved effective config, including referenced strategy/risk
profiles and resolved paths:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli config validate --config configs/backtest.yaml
PYTHONPATH=src .venv/bin/python -m qts.cli config explain --config configs/backtest.yaml
PYTHONPATH=src .venv/bin/python -m qts.cli config dump --config configs/backtest.yaml --format json
```

Download Alpaca SIP historical K-line bars to CSV or Parquet:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_data.py --config configs/data/alpaca_sip_bars.yaml
```

The downloader supports `1min`, `5min`, `15min`, `1hour`, and `1day` levels.
The default config writes a partitioned dataset under `data/alpaca` using
`timeframe`, `symbol`, and `date` partitions. Alpaca is requested for the full
configured interval, then rows are filtered locally to regular US equity
session starts `[09:30, 16:00)` in `America/New_York`. The downloader is
currently SIP-only. The session filter uses the shared US equity calendar, so
holidays and early closes are filtered locally as well. Backtests that read a
mixed partitioned dataset should set
`market_data.bar_interval` such as `1Min` or `5Min` to avoid mixing minute
aggregations. Use CLI overrides for quick experiments:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_data.py \
  --config configs/data/alpaca_sip_bars.yaml \
  --symbols SPY,QQQ \
  --timeframe 5min \
  --format parquet \
  --output data/alpaca_parquet
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

Initialize the Phase 6 paper runtime without credentials by using mock mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py --config configs/paper_alpaca.yaml --mock --dry-run
```

With Alpaca paper credentials in `.env`, omit `--mock` to initialize against the
paper API:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py --config configs/paper_alpaca.yaml --dry-run
```

Initialize the Phase 9 IBKR paper runtime in credential-free mock mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py --config configs/paper_ibkr.yaml --mock --dry-run
```

Run the Phase B1 fake-stream paper config without credentials:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py --config configs/paper_fake_stream.yaml --max-events 2 --dry-run
```

Run the Phase B2a Alpaca stream adapter smoke config without credentials:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py --config configs/paper_alpaca_stream_mock.yaml --max-events 3 --dry-run
```

IBKR order tickets require `broker.account_id` and a
`broker.safety.symbol_conids` mapping. IBKR order responses that require a
manual reply confirmation fail closed; automatic reply confirmation is not
enabled.

Train the Phase 7 fixture directional model into a local model registry:

```bash
PYTHONPATH=src .venv/bin/python scripts/train_model.py --config configs/ml/directional_baseline.yaml
```

Initialize the Phase 8 guarded live engine in dry-run mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_live_trading.py --config configs/live_alpaca.yaml --dry-run --confirm-live-safety
```

This dry-run command validates safety gates, broker/account scaffolding,
reconciliation, and health checks. It does not submit live orders.
