# Operational Runbooks

These runbooks cover the Phase 8 guarded live-trading foundation. Live trading
remains disabled by default; dry-run initialization is the supported operational
readiness path in this phase.

## Live Safety Gate

Before a `LIVE` runtime can initialize, the config must explicitly set:

- `broker.safety.live_enabled: true`
- `broker.safety.allowed_symbols`
- `broker.safety.allowed_account_ids`
- `broker.safety.max_order_notional` or `broker.safety.max_order_quantity`
- `market_session` with a supported exchange/provider, or the default
  fail-closed US equity session settings

Non-dry-run live mode additionally requires
`broker.safety.confirm_live_trading: true`, but real live brokerage submission is
still not enabled by Phase 8.

Dry-run initialization can be exercised locally:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_live_trading.py --config configs/live_alpaca.yaml --dry-run --confirm-live-safety
```

## Health Checks

The Phase 8 live engine runs:

- broker connectivity checks,
- shared market-session checks,
- broker/internal reconciliation checks,
- engine state reporting.

Any `CRITICAL` health result should be treated as a stop condition. Operators
should inspect the health summary, alert payload, and runtime metrics before
attempting another initialization.

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
resolved. Phase 8 includes in-memory and logging sinks; production notification
channels remain future work.

## Recovery Behavior

The recovery manager follows a conservative default:

1. Record a runtime failure metric.
2. Emit a critical alert.
3. Stop the engine when an engine handle is available.

Do not resume trading automatically after a critical failure. Run health checks
and reconciliation first.

## Order Safety

Every future live order path must validate normalized `OrderRequest` objects
against the live safety policy before broker submission. The scaffold also
rejects order timestamps outside the configured market session. Real live
submission remains disabled until a later production-live phase.
