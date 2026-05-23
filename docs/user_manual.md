# Quant Trading System V3 User Manual

This manual is for running, configuring, and safely operating the current
Quant Trading System V3 repository. It complements the root architecture
documents, which remain the source of truth for design decisions:

- `SYSTEM_DESIGN.md`
- `PHASE_PLAN.md`
- `INTERFACES.md`
- `DATA_MODELS.md`
- `DECISIONS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

The current implementation is complete through Phase 9. It supports local
backtests, report generation, mocked paper initialization for Alpaca and IBKR,
an offline ML baseline workflow, and guarded live dry-run initialization. Real
live broker order submission is intentionally disabled.

## 1. Safety Model

This system is built around explicit mode boundaries:

| Mode | Config | Current Behavior |
|---|---|---|
| Backtest | `configs/backtest.yaml`, `configs/backtest_fixture.yaml` | Runs deterministic local bar replay with simulated brokerage fills. |
| Paper | `configs/paper_alpaca.yaml`, `configs/paper_ibkr.yaml` | Initializes a paper brokerage path. Mock mode works without credentials. |
| Live | `configs/live_alpaca.yaml` | Guarded dry-run scaffold only. Real live submission is disabled. |

Important safety constraints:

- Strategies never submit orders directly.
- Risk must approve or reject strategy output before execution.
- Execution talks only to the normalized `Brokerage` interface.
- Vendor API objects are converted at adapter boundaries.
- Paper/live engines currently consume externally supplied market events; they
  do not own a continuous live market data stream.
- IBKR order replies that require manual confirmation fail closed and are not
  auto-confirmed.
- Live order submission requires a future documented phase.

## 2. Local Setup

Use Python 3.11 or newer. The repository is intentionally usable with only the
standard library for core tests and fixture workflows.

Create or reuse the virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

Install the project for development when package indexes are available:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

For Parquet-backed historical data, install the optional data extra:

```bash
.venv/bin/python -m pip install -e ".[data]"
```

If you do not install the package, set `PYTHONPATH=src` when running scripts:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli --config configs/backtest.yaml
```

## 3. Environment Variables

Copy the example file before adding local secrets:

```bash
cp .env.example .env
```

Do not commit `.env`. The repository expects secrets and broker endpoint
overrides to come from environment variables, not YAML.

Supported variables:

| Variable | Used By | Purpose |
|---|---|---|
| `QTS_RUNTIME_MODE` | local operator convention | Optional local mode hint. |
| `QTS_LOG_LEVEL` | local operator convention | Optional log level hint. |
| `ALPACA_API_KEY_ID` | Alpaca adapter | Alpaca API key. |
| `ALPACA_SECRET_KEY` | Alpaca adapter | Alpaca API secret. |
| `ALPACA_PAPER_BASE_URL` | `configs/paper_alpaca.yaml` | Alpaca paper endpoint override. |
| `ALPACA_LIVE_BASE_URL` | `configs/live_alpaca.yaml` | Alpaca live endpoint override. Live submission remains disabled. |
| `IBKR_ACCESS_TOKEN` | IBKR adapter | Optional IBKR bearer token if using a real Web API endpoint. |
| `IBKR_BASE_URL` | `configs/paper_ibkr.yaml` | IBKR Web API endpoint override. |

## 4. Running Tests

Run the standard-library test suite:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

If the development extra is installed:

```bash
.venv/bin/python -m pytest
```

Run lint checks:

```bash
.venv/bin/ruff check .
```

Use `git diff --check` before committing to catch trailing whitespace:

```bash
git diff --check
```

## 5. Configuration Basics

Configuration files are YAML mappings loaded by `qts.core.load_runtime_config`.
Mode-specific files usually extend `configs/base.yaml`.

Core fields:

| Field | Meaning |
|---|---|
| `runtime.mode` | `BACKTEST`, `PAPER`, or `LIVE`. |
| `symbols` | Default symbol universe inherited from `base.yaml`. |
| `timeframe` | Current default is `MINUTE`. |
| `market_data` | Provider and path/settings. |
| `broker` | Broker implementation and safety settings. |
| `strategies` | Strategy definitions and parameters. |
| `risk` | Sizing and risk rules. |
| `execution` | Execution policy such as `allow_fractional`. |
| `portfolio` | Starting cash or account currency settings. |
| `reporting` | Output locations for backtest artifacts. |
| `monitoring` | Runtime monitoring switches. |

Validate a config without running a full workflow:

```bash
PYTHONPATH=src .venv/bin/python -m qts.cli --config configs/backtest_fixture.yaml
```

## 6. Backtesting

The quickest runnable backtest uses the fixture config:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_backtest.py --config configs/backtest_fixture.yaml
```

Expected output includes:

- run ID,
- fill count,
- total return,
- summary artifact path.

The fixture config uses:

- local CSV market data from `tests/fixtures/market_data/backtest_sma_cross.csv`,
- SMA crossover strategy,
- fixed quantity sizing,
- `BacktestBrokerage`,
- next-bar-open fill policy,
- output under `artifacts/reports/`.

Run a custom historical backtest by editing or copying `configs/backtest.yaml`.
For Parquet input, install the data extra and point `market_data.path` to a
Parquet file with normalized bar columns.

### Backtest Data Columns

CSV and Parquet bar data should include:

| Column | Required | Notes |
|---|---:|---|
| `symbol` | yes | Normalized to uppercase. |
| `timestamp` | yes | Timezone-aware or parseable timestamp. |
| `open` | yes | Non-negative. |
| `high` | yes | Must be at least open, close, and low. |
| `low` | yes | Must be at most open, close, and high. |
| `close` | yes | Non-negative. |
| `volume` | yes | Non-negative. |
| `timeframe` | no | Defaults to config timeframe. |
| `vwap` | no | Optional non-negative value. |
| `trade_count` | no | Optional non-negative integer. |
| `source` | no | Provider label. |

## 7. Report Generation

Generate report artifacts by running:

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_report.py --config configs/backtest_fixture.yaml
```

Artifacts are written to `artifacts/reports/` by default:

- summary Markdown,
- metrics JSON,
- equity curve CSV,
- trades CSV,
- cash ledger CSV,
- config JSON.

Override the output directory:

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_report.py \
  --config configs/backtest_fixture.yaml \
  --output-dir artifacts/reports/manual-check
```

## 8. Alpaca Paper Runtime

Mock mode initializes the Alpaca paper path without credentials:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py \
  --config configs/paper_alpaca.yaml \
  --mock \
  --dry-run
```

With real Alpaca paper credentials in `.env`, omit `--mock`:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py \
  --config configs/paper_alpaca.yaml \
  --dry-run
```

Current limitations:

- Alpaca is used only as a broker adapter.
- Alpaca market data is not implemented.
- Paper events are expected to be externally supplied to `PaperTradingEngine`.
- Fill updates are derived from polling filled-quantity deltas.

## 9. IBKR Paper Runtime

Mock mode initializes the IBKR paper path without credentials:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_paper_trading.py \
  --config configs/paper_ibkr.yaml \
  --mock \
  --dry-run
```

IBKR paper configuration requires:

- `broker.account_id`,
- `broker.safety.symbol_conids`,
- quantity-based order sizing.

Example:

```yaml
broker:
  broker_type: ibkr_paper
  paper: true
  account_id: DU123456
  safety:
    symbol_conids:
      SPY: 756733
```

Current limitations:

- IBKR market data is not implemented.
- IBKR live submission is disabled.
- Notional-only IBKR order requests are rejected.
- IBKR order responses requiring manual reply confirmation fail closed.

## 10. ML Workflow

Train the dependency-free directional baseline model:

```bash
PYTHONPATH=src .venv/bin/python scripts/train_model.py \
  --config configs/ml/directional_baseline.yaml
```

The fixture ML config uses:

- CSV data from `tests/fixtures/market_data/ml_directional.csv`,
- returns and SMA features,
- forward-return labels,
- chronological train/validation/test split,
- filesystem registry under `artifacts/models/`.

Override the model registry output directory:

```bash
PYTHONPATH=src .venv/bin/python scripts/train_model.py \
  --config configs/ml/directional_baseline.yaml \
  --output-dir artifacts/models/manual-check
```

The runtime ML strategy adapter lives in `qts.strategies.ml_strategy` and loads
registered models through `qts.ml.inference`.

## 11. Live Dry-Run Runtime

Initialize guarded live dry-run mode:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_live_trading.py \
  --config configs/live_alpaca.yaml \
  --dry-run \
  --confirm-live-safety
```

This validates:

- runtime mode,
- live safety gate settings,
- dry-run brokerage scaffold,
- account allowlist,
- symbol allowlist,
- max order caps,
- reconciliation,
- health checks.

It does not submit live broker orders.

Without `--confirm-live-safety`, the live engine should fail closed. That is
expected.

## 12. Common Configuration Changes

### Change Strategy Windows

Edit a strategy block:

```yaml
strategies:
  - strategy_id: sma_cross_v1
    strategy_type: sma_crossover
    symbols: [SPY]
    parameters:
      fast_window: 10
      slow_window: 30
```

For fixture backtests, update `configs/backtest_fixture.yaml`.

### Change Fixed Position Size

Use fixed quantity:

```yaml
risk:
  sizing_method: fixed_quantity
  sizing_parameters:
    quantity: 10
```

Use fixed notional:

```yaml
risk:
  sizing_method: fixed_notional
  sizing_parameters:
    notional_per_trade: 1000
```

IBKR currently requires quantity-based order requests.

### Change Symbols

Update:

- top-level `symbols`,
- each strategy `symbols`,
- risk `allowed_symbols` if enabled,
- broker symbol mappings such as IBKR `symbol_conids`.

### Change Backtest Fill Policy

Backtest broker supports:

- `next_bar_open`,
- `next_bar_close`,
- `next_bar_typical_price`,
- `quote_bid_ask`.

Example:

```yaml
broker:
  broker_type: backtest
  fill_policy: next_bar_open
```

## 13. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: qts` | Package not installed and `PYTHONPATH` not set. | Run with `PYTHONPATH=src` or install with `pip install -e ".[dev]"`. |
| Config says no enabled strategies | Every strategy has `enabled: false` or list is empty. | Enable at least one strategy. |
| Backtest config requires start and end | `runtime.mode` is `BACKTEST` but date range missing. | Add `date_range.start` and `date_range.end`. |
| CSV data validation error | Missing or invalid bar columns. | Check required columns and timestamp format. |
| Paper engine rejects market data provider | Paper/live currently require `external_events`. | Set `market_data.provider: external_events`. |
| Alpaca paper fails without credentials | Real adapter selected without env vars. | Use `--mock` or populate `.env`. |
| IBKR requires conid | No IBKR contract mapping for symbol. | Add `broker.safety.symbol_conids`. |
| IBKR rejects notional orders | Adapter currently supports quantity orders only. | Use fixed quantity sizing. |
| Live engine fails safety validation | Missing explicit safety confirmation. | Use dry-run command with `--confirm-live-safety`; do not bypass for real trading. |

## 14. Recommended Operator Checklist

Before running any non-mock broker workflow:

1. Confirm the config path.
2. Confirm `runtime.mode`.
3. Confirm `market_data.provider`.
4. Confirm broker type and paper/live setting.
5. Confirm credentials are in `.env`, not YAML.
6. Confirm risk sizing and max order caps.
7. Confirm allowed symbols and account IDs.
8. Run tests.
9. Run mock or dry-run initialization first.
10. Inspect logs and reconciliation status.

Before adding real live submission in a future phase:

1. Extend `PHASE_PLAN.md`.
2. Add an ADR in `DECISIONS.md`.
3. Add explicit tests for every safety gate.
4. Keep live order validation centralized in monitoring/safety.
5. Preserve broker adapter fail-closed behavior.

## 15. Glossary

| Term | Meaning |
|---|---|
| Domain model | Stable internal data object from `qts.domain`. |
| Signal | Strategy directional output before sizing. |
| TradeIntent | Sized or unsized intent that risk can evaluate. |
| RiskDecision | Approval, rejection, or modification from risk. |
| OrderRequest | Normalized broker-ready order request. |
| Order | Normalized broker order state. |
| Fill | Normalized execution fill event. |
| Broker adapter | Implementation of the `Brokerage` interface. |
| Integration adapter | Low-level vendor client and payload mapping. |
| DataPortal | Strategy-facing market data and feature read interface. |
| Feature schema | Stable feature names and schema version used for runtime consistency. |
