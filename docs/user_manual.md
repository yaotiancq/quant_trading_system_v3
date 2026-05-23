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

The current implementation is complete through Phase 10. It supports Alpaca SIP
historical bar downloads, local backtests, report generation, mocked paper
initialization for Alpaca and IBKR, an offline ML baseline workflow, and guarded
live dry-run initialization. Real live broker order submission is intentionally
disabled.

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
| `ALPACA_DATA_BASE_URL` | `configs/data/alpaca_sip_bars.yaml` | Alpaca market data endpoint override. |
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

## 6. Download Alpaca SIP Historical K-Line Data

Use `scripts/download_data.py` to download historical US stock bars from Alpaca
SIP into a normalized CSV or Parquet file. CSV output is compatible with
`CSVBarProvider`; Parquet output is compatible with `LocalParquetProvider` when
the optional data dependencies are installed. Both formats can be used by
backtest configs.

Default command:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_data.py \
  --config configs/data/alpaca_sip_bars.yaml
```

Supported K-line levels:

| User Value | Alpaca Timeframe | Domain `timeframe` |
|---|---|---|
| `1min` | `1Min` | `MINUTE` |
| `5min` | `5Min` | `MINUTE` |
| `15min` | `15Min` | `MINUTE` |
| `1hour` | `1Hour` | `HOUR` |
| `1day` | `1Day` | `DAY` |

The exact Alpaca aggregation is also written to the output as `bar_interval`
and `alpaca_timeframe`.
For example, a 5-minute download has `timeframe=MINUTE` for compatibility with
the current domain enum and `bar_interval=5Min` for filtering/auditability.
Backtest configs should set `market_data.bar_interval` when reading a dataset
root that may contain multiple minute aggregations.

The config file owns user settings:

```yaml
market_data:
  provider: alpaca_sip
  symbols: [SPY]
  timeframe: 1min
  start: 2024-01-02T14:30:00Z
  end: 2024-01-02T21:00:00Z
  # Current downloader support is SIP-only.
  feed: sip
  adjustment: raw
  limit: 10000
  base_url_env: ALPACA_DATA_BASE_URL
  # Alpaca is requested for the full interval; rows are filtered locally.
  session_filter:
    enabled: true
    timezone: America/New_York
    start: "09:30"
    end: "16:00"

credentials:
  api_key_id_env: ALPACA_API_KEY_ID
  secret_key_env: ALPACA_SECRET_KEY

output:
  # Supported values: csv, parquet.
  format: csv
  # Supported values: partitioned, single_file.
  layout: partitioned
  directory: data/alpaca
  # Creates directories such as:
  # data/alpaca/timeframe=1Min/symbol=SPY/date=2024-01-02/
  partition_by: [timeframe, symbol, date]
  # Available placeholders: {feed}, {symbols}, {symbol}, {timeframe}, {start},
  # {end}, {date}, {adjustment}, {format}, {alpaca_timeframe}, {source}.
  filename_template: bars_{start}_{end}.{format}
```

With this layout, multiple symbols and dates are written as separate partition
files instead of one large file. Changing `format` automatically changes the
generated file extension. To write Parquet, install the data extra and set:

```yaml
output:
  format: parquet
  layout: partitioned
  directory: data/alpaca
  partition_by: [timeframe, symbol, date]
  filename_template: bars_{start}_{end}.{format}
```

You can still use `layout: single_file` with a fixed `output.path`, but that is
intended for small fixtures and ad hoc exports. If `output.path` ends with
`.csv` or `.parquet`, the extension must match `output.format`.

The regular-session filter is applied after download. For minute bars on US
equities, this keeps bar start times where the timestamp converted to
`America/New_York` is greater than or equal to `09:30` and less than `16:00`.
For example, during Eastern daylight time, a `20:00:00Z` bar starts at `16:00`
ET and is excluded. Set `session_filter.enabled: false` only when you want
extended-hours data.

Quick CLI overrides are available:

```bash
PYTHONPATH=src .venv/bin/python scripts/download_data.py \
  --config configs/data/alpaca_sip_bars.yaml \
  --symbols SPY,QQQ \
  --timeframe 15min \
  --format parquet \
  --start 2024-01-02T14:30:00Z \
  --end 2024-01-31T21:00:00Z \
  --output data/alpaca_parquet
```

Output columns in both formats:

| Column | Meaning |
|---|---|
| `symbol` | Stock symbol. |
| `timestamp` | UTC bar timestamp. |
| `timeframe` | Broad system timeframe: `MINUTE`, `HOUR`, or `DAY`. |
| `open`, `high`, `low`, `close` | OHLC values. |
| `volume` | Bar volume. |
| `vwap` | Alpaca VWAP value when present. |
| `trade_count` | Alpaca trade count when present. |
| `source` | Source label such as `alpaca_sip_5Min`. |
| `alpaca_timeframe` | Exact Alpaca aggregation, such as `5Min`. |

To backtest downloaded CSV data, point a backtest config at the dataset root:

```yaml
market_data:
  provider: local_csv
  path: data/alpaca
  adjustment: RAW

timeframe: MINUTE
```

For Parquet data, set `market_data.provider: local_parquet` and use the
partitioned dataset root.

Notes:

- Alpaca SIP access depends on your account subscription and permissions.
- The API request uses the full configured `start`/`end`; session boundaries are
  controlled by local filtering.
- The script uses paginated requests and writes returned rows to one or more
  partition files.
- If Alpaca returns request IDs, the script prints them for support/debugging.

## 7. Backtesting

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
By default, that template reads the partitioned CSV dataset under `data/alpaca`,
which is the output location used by `configs/data/alpaca_sip_bars.yaml`.
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

## 8. Report Generation

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

## 9. Alpaca Paper Runtime

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

- In the paper runtime, Alpaca is used only as a broker adapter.
- Alpaca live market data streams are not implemented; historical SIP downloads
  are available through `scripts/download_data.py`.
- Paper events are expected to be externally supplied to `PaperTradingEngine`.
- Fill updates are derived from polling filled-quantity deltas.

## 10. IBKR Paper Runtime

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

## 11. ML Workflow

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

## 12. Live Dry-Run Runtime

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

## 13. Common Configuration Changes

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

## 14. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: qts` | Package not installed and `PYTHONPATH` not set. | Run with `PYTHONPATH=src` or install with `pip install -e ".[dev]"`. |
| Config says no enabled strategies | Every strategy has `enabled: false` or list is empty. | Enable at least one strategy. |
| Backtest config requires start and end | `runtime.mode` is `BACKTEST` but date range missing. | Add `date_range.start` and `date_range.end`. |
| CSV data validation error | Missing or invalid bar columns. | Check required columns and timestamp format. |
| Alpaca data download returns 403 | Missing credentials, invalid credentials, or SIP permission issue. | Check `.env`, Alpaca account permissions, and subscription. |
| Alpaca download level rejected | Unsupported K-line level. | Use `1min`, `5min`, `15min`, `1hour`, or `1day`. |
| Paper engine rejects market data provider | Paper/live currently require `external_events`. | Set `market_data.provider: external_events`. |
| Alpaca paper fails without credentials | Real adapter selected without env vars. | Use `--mock` or populate `.env`. |
| IBKR requires conid | No IBKR contract mapping for symbol. | Add `broker.safety.symbol_conids`. |
| IBKR rejects notional orders | Adapter currently supports quantity orders only. | Use fixed quantity sizing. |
| Live engine fails safety validation | Missing explicit safety confirmation. | Use dry-run command with `--confirm-live-safety`; do not bypass for real trading. |

## 15. Recommended Operator Checklist

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

## 16. Glossary

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
