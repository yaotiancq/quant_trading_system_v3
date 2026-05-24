# Operational Runbooks

These runbooks cover the guarded live-trading foundation through Major
Architecture Phase D2. Live trading remains disabled by default; dry-run
initialization, deterministic broker-event synchronization, and manually gated
live order submission through the selected Alpaca live adapter are the
supported operational readiness paths in this phase.

## Live Safety Gate

Before a `LIVE` runtime can initialize, the config must explicitly set:

- `broker.safety.live_enabled: true`
- `broker.safety.allowed_symbols`
- `broker.safety.allowed_account_ids`
- `broker.safety.max_order_notional` or `broker.safety.max_order_quantity`
- `market_session` with a supported exchange/provider, or the default
  fail-closed US equity session settings

Non-dry-run live mode additionally requires
`broker.safety.confirm_live_trading: true`. Manual live order submission also
requires `broker.safety.enable_order_submission: true` and a matched
reconciliation check immediately before submission.

Dry-run initialization can be exercised locally:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_live_trading.py --config configs/live_alpaca.yaml --dry-run --confirm-live-safety
```

## Health Checks

The guarded live engine runs:

- broker connectivity checks,
- shared market-session checks,
- broker/internal reconciliation checks,
- engine state reporting.

Any `CRITICAL` health result should be treated as a stop condition. Operators
should inspect the health summary, alert payload, and runtime metrics before
attempting another initialization.

## Runtime Market Data Stream Reliability

Paper runtime event loops expose stream status counters in the `event_loop`
health payload:

- `disconnect_count`
- `reconnect_count`
- `heartbeat_miss_count`
- `source_run_count`
- `stopped_reason`

`market_data.reconnect.enabled` should remain false for local mock streams
unless a test injects a source factory. Real streaming transports must use
bounded reconnect attempts and fail closed when reconnect is exhausted.

`market_data.heartbeat.timeout_seconds` is a deterministic event timestamp gap
check in this phase. A miss should be investigated as stale or interrupted
market data before any paper/live runtime is resumed.

## Live Decision Preview

Dry-run live bar events may produce decision previews. A preview means the
engine ran feature updates, strategy logic, risk evaluation, order-request
construction, and live safety validation. It does not mean an order was sent.

Treat `preview_status: safety_rejected` as a blocked would-be order. Inspect the
preview `error`, risk reasons, order size, symbol allowlist, market-session
state, and account safety caps before changing any configuration.

## Manual Live Order Submission

`LiveEngine.submit_live_order(...)` is the only Phase D1 live submission path.
It accepts a normalized `OrderRequest` that has already been built by operator
code or a controlled script. It does not automatically submit strategy decision
previews.

Before enabling `broker.safety.enable_order_submission`, confirm:

- `dry_run` and `mock_mode` are false,
- `confirm_live_trading` is true,
- account and symbol allowlists are populated,
- max order caps are intentionally low,
- the market session is open for the order timestamp,
- reconciliation is matched.

If any validation fails, keep the engine stopped or in dry-run mode and resolve
the safety issue before retrying.

## Alpaca Live Adapter Enablement

Phase D2 permits `LiveEngine` to construct `AlpacaBrokerage` for
`broker_type: alpaca_live` only after the same D1 live submission gates pass.
The live adapter still uses normalized `OrderRequest`, `Order`, `Fill`,
`Account`, and `Position` objects at the system boundary.

Before constructing a non-dry-run Alpaca live adapter, confirm:

- `broker.paper` is false,
- `dry_run` and `mock_mode` are false,
- `live_enabled`, `confirm_live_trading`, and `enable_order_submission` are true,
- live credentials are available through `broker.credential_env_keys`,
- `ALPACA_LIVE_BASE_URL` or `broker.base_url` points to the intended endpoint,
- account and symbol allowlists match the target live account.

IBKR live remains fail-closed. Automated strategy-driven live submission is
still future Phase D3 work.

## Broker Lifecycle Synchronization

Paper order and fill polling is normalized into `BrokerEvent` updates before
state changes are applied. Duplicate fill IDs are skipped, and stale order
updates should not regress the tracked lifecycle state. Phase C3 also adds
checkpointed broker-event sync with duplicate suppression, out-of-order checks,
optional timestamp gap fail-closed policy, and reconciliation before and after
each sync run.

If paper portfolio state looks wrong after polling:

1. Inspect the broker adapter's normalized `Order` and `Fill` payloads.
2. Confirm repeated fills have stable `fill_id` values.
3. Confirm order updates have monotonic `updated_at` values and nondecreasing
   `filled_quantity`.
4. Re-run reconciliation before sending more paper orders.
5. If using `sync_broker_events(...)`, inspect `duplicate_count`, `gap_count`,
   `out_of_order_count`, `stopped_reason`, and the before/after reconciliation
   payload.
6. Treat missing real vendor push-stream updates as expected until a later
   phase adds broker event stream transports.

Phase C2 adds mockable Alpaca/IBKR broker event adapter boundaries, and Phase C3
adds engine sync/checkpoint plumbing. The in-memory clients are useful for tests
and local development, but they are not real websocket/SSE transports.
Operators should continue relying on polling and reconciliation for real paper
broker state until a later phase adds live broker stream ownership.

## Reconciliation Mismatch

When reconciliation reports `mismatch`:

1. Stop the live engine or keep it stopped.
2. Compare broker account cash/equity against internal portfolio cash/equity.
3. Compare position quantities, average cost, and market value by symbol.
4. Resolve the source of mismatch before allowing order submission.
5. Re-run dry-run initialization and confirm the reconciliation check is `OK`.

## Alert Handling

Alerts include severity, source, message, timestamp, and structured details. A
`CRITICAL` alert means trading must stay disabled until the underlying issue is
resolved. The current system includes in-memory and logging sinks; production notification
channels remain future work.

## Recovery Behavior

The recovery manager follows a conservative default:

1. Record a runtime failure metric.
2. Emit a critical alert.
3. Stop the engine when an engine handle is available.

Do not resume trading automatically after a critical failure. Run health checks
and reconciliation first.

## Order Safety

Every live order path must validate normalized `OrderRequest` objects against
the live safety policy before broker submission. The scaffold also rejects order
timestamps outside the configured market session. Automated strategy-driven live
submission remains disabled until a later production-live phase.
