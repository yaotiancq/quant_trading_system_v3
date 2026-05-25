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

Major Architecture Phase F3 is complete. The repository now includes the package
layout, validated domain models and enums, core configuration loading, clocks,
common exceptions, logging setup, local market data providers, a config-driven
Alpaca SIP historical bar downloader, a shared US equity calendar/session
service, deterministic replay, reusable batch indicators, feature schemas,
feature pipelines, broker-agnostic example strategies, a risk engine with
position sizing and basic rules, an execution engine, order manager/router,
normalized broker lifecycle events, checkpointed broker-event synchronization,
mockable Alpaca/IBKR broker push-event adapter boundaries, normalized brokerage
protocol, simulated BacktestBrokerage, internal portfolio accounting, a
deterministic backtest engine, reporting metrics, artifacts, and optional
static SVG chart diagnostics, a
dependency-free Alpaca paper brokerage adapter, a paper trading engine
initialization path, configuration templates, an offline ML workflow, a
filesystem model registry with manifest/schema-hash contracts, runtime ML
inference with opt-in approval/stage policy and runtime diagnostics, an ML
signal strategy adapter,
monitoring and alert helpers, reconciliation health checks, guarded live safety
gates, dry-run `LiveEngine` scaffolding, a manual live order submission safety
envelope, gated Alpaca live adapter construction, optional automated live
decision submission with a kill switch and fail-stop behavior, a
dependency-free IBKR paper brokerage foundation, operational runbooks, and
tests.

Live order submission remains disabled by default and requires explicit
non-dry-run production gates. The documented implementation phases are complete;
the final system design and implementation review is complete. Future work
should start from a new documented phase or requirement.

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
                  Order requests, lifecycle events, manager, router, fill handler, engine
src/qts/brokers/  Brokerage protocol, BacktestBrokerage, AlpacaBrokerage, IBKRBrokerage
src/qts/integrations/
                  Low-level vendor clients and mapping adapters
src/qts/portfolio/
                  Portfolio accounting, ledgers, snapshots, reconciliation
src/qts/engines/  BacktestEngine, PaperTradingEngine, and runtime event loop
src/qts/reporting/
                  Backtest metrics, report artifact export, and optional SVG charts
src/qts/ml/       Offline datasets, labels, splits, training, registry, manifests, inference
src/qts/monitoring/
                  Health checks, metrics, alerts, recovery, safety gates
scripts/          Local data download, backtest, report, paper, ML, and live dry-run commands
docs/             User manual, system handbook, and operational runbooks
tests/            Smoke, unit, and integration tests through Phase F3 and final review
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

Runtime event loops support deterministic reconnect and heartbeat/data-gap
policy through `market_data.reconnect` and `market_data.heartbeat`. Reconnects
require an explicit source factory, and current tests do not sleep or open real
network streams.

Live dry-run event handling can produce guarded decision previews. These
previews run the feature, strategy, risk, order-request, and live-safety path,
then stop before broker submission.

Paper broker order/fill polling is normalized into `BrokerEvent` lifecycle
updates before the execution and portfolio layers apply state changes. Duplicate
fill events and stale order updates are ignored by the synchronization path.
Alpaca and IBKR push-style broker payloads can also be normalized through
in-memory adapter clients for deterministic tests; real broker stream transports
remain future work.

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

Generate report artifacts with static SVG equity and drawdown diagnostics:

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_report.py \
  --config configs/backtest_fixture.yaml \
  --output-dir artifacts/reports/fixture-with-charts \
  --generate-plots
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

Train the fixture directional model into a local model registry:

```bash
PYTHONPATH=src .venv/bin/python scripts/train_model.py --config configs/ml/directional_baseline.yaml
```

The training command writes both `model.json` and `manifest.json`; the manifest
captures the model stage, feature schema version, ordered feature names, and
feature-schema hash. Use `FileModelRegistry.approve_model(...)` to promote a
validated model before running configs that set `require_approved_model: true`.

Initialize the guarded live engine in dry-run mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_live_trading.py --config configs/live_alpaca.yaml --dry-run --confirm-live-safety
```

This dry-run command validates safety gates, broker/account scaffolding,
reconciliation, and health checks. It does not submit live orders. Manual live
submission additionally requires `broker.safety.enable_order_submission: true`
and a non-dry-run live brokerage. The selected Alpaca live adapter can be
constructed only after those same explicit gates pass; automated strategy
submissions additionally require `broker.safety.enable_automated_submission:
true` and `broker.safety.automated_submission_kill_switch: false`.
