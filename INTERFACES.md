# INTERFACES.md

# Core Interfaces and Contracts

## 1. Interface Conventions

This document defines module contracts. It is not application code.

General conventions:

- All domain objects are defined in `DATA_MODELS.md`.
- All timestamps are timezone-aware and normalized to UTC unless display formatting requires local time.
- Vendor API objects must not cross module boundaries.
- Public interface changes require updates to this document.
- Implementations may use abstract base classes, protocols, or equivalent Python typing constructs.

## 2. Ownership Rules

| Interface | Owned By | Implemented By | Consumed By |
|---|---|---|---|
| `MarketCalendar` / `MarketSessionService` | `calendar/` | built-in US equity provider | market data, engines, monitoring, brokers |
| `MarketDataProvider` | `market_data/` | local, replay, live providers | engines, data portal |
| `DataPortal` | `market_data/` | default data portal | strategies, features, engines |
| `Indicator` | `features/` | indicator classes/functions | feature pipeline |
| `FeaturePipeline` | `features/` | concrete pipelines | strategies, ML, engines |
| `Strategy` | `strategies/` | rule-based and ML strategies | engines |
| `ModelRegistry` | `ml/` | filesystem registry | training, inference, ML strategies |
| `MLModelInference` | `ml/` | model inference adapters | ML strategies |
| `RiskRule` | `risk/` | concrete risk rules | risk engine |
| `RiskEngine` | `risk/` | default risk engine | engines |
| `PositionSizer` | `risk/` | sizing models | risk engine |
| `ExecutionEngine` | `execution/` | default execution engine | engines |
| `OrderManager` | `execution/` | default order manager | execution engine |
| `OrderRouter` | `execution/` | default order router | execution engine |
| `BrokerEvent` helpers | `execution/` | polling/event adapters | execution engine, paper/live engines |
| `BrokerEventSource` | `execution/` / `integrations/` | Alpaca/IBKR event adapters | future engine synchronization |
| `BrokerEventSyncLoop` | `execution/` | default sync loop | paper/live engines |
| `Brokerage` | `brokers/` | backtest, Alpaca, IBKR | order router, engines |
| `BacktestBrokerage` | `brokers/backtest/` | backtest implementation | backtest engine |
| `Portfolio` | `portfolio/` | default portfolio | engines, risk, reporting |
| `BacktestEngine` | `engines/` | default backtest engine | scripts, CLI |
| `LiveEngine` | `engines/` | paper/live engine variants | scripts, CLI |
| `Reporter` | `reporting/` | report generators | engines, scripts |

## 3. MarketDataProvider

### Purpose

Provide normalized market data without exposing vendor-specific APIs.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `get_history` | symbols, start, end, timeframe, adjustment policy | sequence/table of `Bar` or `Quote` | Historical batch access. |
| `iter_replay` | symbols, start, end, timeframe | iterator of market data events | Deterministic replay for backtests. |
| `get_latest_bar` | symbol | optional `Bar` | For live/paper polling providers. |
| `get_latest_quote` | symbol | optional `Quote` | For quote-aware execution or monitoring. |
| `subscribe` | symbols, data types, callback | subscription handle | Optional for live providers. |
| `close` | none | none | Release resources. |

### Historical Download Helpers

Config-driven download helpers may live under `market_data/` when they produce
normalized local data for providers to consume. The Alpaca SIP downloader writes
CSV or Parquet rows compatible with `CSVBarProvider` and `LocalParquetProvider`.
The default layout is a partitioned dataset by exact timeframe, symbol, and
date; providers recursively read matching files when given a dataset directory.
The API request interval remains the configured `start`/`end`, and regular
session inclusion is enforced locally on returned rows.
The downloader does not submit orders and does not share code with broker
adapters.

### Error Behavior

- Missing required columns: raise data validation error.
- Unsupported timeframe: raise configuration or data provider error.
- Provider unavailable: raise provider connection error or return explicit failure result depending on runtime mode.

### Stability Notes

The interface is stable. New providers must conform to it rather than forcing changes upstream.

## 3a. MarketCalendar and MarketSessionService

### Purpose

Resolve exchange sessions and answer tradability questions without duplicated
weekday-only logic.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `session_for_date` | local session date | optional `MarketSession` | Returns None for holidays/weekends. |
| `session_for_timestamp` | timestamp | optional `MarketSession` | Converts timestamp to configured exchange timezone. |
| `is_regular_session` | timestamp | bool | Uses inclusive open and exclusive close. |
| `is_tradable` | timestamp | bool | Applies regular-only or extended-hours config. |
| `current_or_next_session` | timestamp | `MarketSession` | Returns current session if still tradable, otherwise next. |
| `next_session_after` | timestamp | `MarketSession` | Finds the next resolvable session. |

### Error Behavior

- Invalid exchange/provider/timezone configuration raises configuration error.
- If a provider cannot resolve a session and `fail_closed` is true, tradability
  checks return false.
- If `fail_closed` is false, unresolved provider failures raise a calendar
  error.

### Stability Notes

The first built-in provider targets US equities for `XNYS` and `NASDAQ`. Future
providers should implement the same interface rather than embedding calendar
logic in engines, broker adapters, or data downloaders.

## 4. DataPortal

### Purpose

Provide a unified read interface to market data and features for strategies and engines.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `get_bars` | symbol, lookback/window, end timestamp | sequence/table of `Bar` | Used by strategies and feature pipelines; replay-bounded portals must not expose bars after the current replay/live timestamp. |
| `get_current_bar` | symbol | optional `Bar` | Current replay/live bar. |
| `get_quote` | symbol | optional `Quote` | Latest quote if available. |
| `get_feature_frame` | symbols, feature names, lookback | `FeatureFrame` | Batch feature access. |
| `advance` | market event | none | Update current data state during replay/live loop. |

### Ownership Rules

- `DataPortal` may compose one or more `MarketDataProvider` instances.
- It must not submit orders.
- It must not own portfolio state.

## 5. Indicator

### Purpose

Define reusable indicator behavior for batch and optional online computation.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `name` | none | string | Stable indicator name. |
| `required_inputs` | none | list of field names | Example: close, high, low, volume. |
| `lookback` | none | integer | Minimum required history. |
| `compute_batch` | input frame/series, parameters | feature series/frame | Used in research/backtesting/ML training. |
| `update` | new `Bar`/`Quote`/value | optional latest value | Optional online/stateful update. |
| `reset` | none | none | Clears online state. |

### Error Behavior

- Insufficient history should return missing values or raise a controlled feature error based on configuration.
- Invalid input schema raises feature schema error.

## 6. FeaturePipeline

### Purpose

Compose indicators and transformations into reusable feature outputs.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `fit` | historical data, optional labels | fitted pipeline or none | Optional; needed for scalers/encoders. |
| `transform_batch` | historical bars/quotes | `FeatureFrame` | For backtests and ML datasets. |
| `update_online` | new market event | `FeatureRecord` | For live/paper inference. |
| `get_schema` | none | feature schema | Used for training-serving consistency. |
| `validate_schema` | feature data | validation result | Detects missing or mismatched features. |

### Stability Notes

The pipeline must produce consistent feature names and types between training and serving.
Explicit empty feature specs mean no computed feature columns. Omitted feature
specs may use the project defaults.

## 7. Strategy

### Purpose

Generate broker-agnostic signals, target positions, or trade intents.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `initialize` | strategy config, data portal, optional context | none | Called once before runtime loop. |
| `on_data` | market event, features, portfolio snapshot | list of `Signal`, `TargetPosition`, or `TradeIntent` | Main signal generation hook. |
| `on_fill` | `Fill` | none | Optional state update after fill. |
| `on_end` | final context | none | Optional cleanup. |
| `name` | none | string | Stable strategy name. |
| `symbols` | none | list of symbols | Strategy universe. |

### Ownership Rules

- Strategy must not submit orders.
- Strategy must not call broker adapters.
- Strategy must not directly mutate portfolio/account state.
- Strategy may maintain its own internal indicator or position-intent state.

### Error Behavior

- Invalid feature schema raises strategy error.
- Unsupported symbol raises strategy error.
- Strategy errors in backtest should fail fast unless configured otherwise.

## 8. MLModelInference

### Purpose

Provide runtime inference for trained ML models.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `load_model` | model URI or registry ID | loaded model handle | Reads registered model and applies configured stage policy. |
| `predict` | `FeatureRecord` or `FeatureFrame` | `ModelPrediction` or list | Runtime prediction. |
| `get_expected_schema` | none | feature schema | Used before prediction. |
| `get_model_metadata` | none | metadata | Model version, training range, metrics. |
| `get_model_manifest` | none | `MLModelManifest` | Loaded model contract with feature-schema hash. |

### Ownership Rules

- This interface only performs inference.
- It does not submit orders.
- It does not decide final position size unless the strategy explicitly interprets prediction that way and risk approves it.
- It must fail closed when a saved model manifest contradicts the model
  artifact contract.
- It may be configured with `require_approved_model=true` or an
  `allowed_model_stages` list. When configured, model loading fails closed if
  the manifest stage does not satisfy policy.

## 8a. ModelRegistry

### Purpose

Persist local model artifacts and portable manifests without exposing runtime
strategies to filesystem details.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `save_model` | model, optional stage | artifact path | Writes `model.json` and `manifest.json`. |
| `load_model` | model id or URI | model handle | Validates manifest contract when present. |
| `load_manifest` | model id or URI | `MLModelManifest` | Reads and validates manifest structure. |
| `manifest_for_model` | model id or URI | `MLModelManifest` | Returns saved manifest or synthesized legacy manifest. |
| `transition_model_stage` | model id or URI, target stage, actor/reason | `MLModelManifest` | Persists stage changes and transition history. |
| `mark_validated` / `approve_model` / `archive_model` | model id or URI, approval metadata | `MLModelManifest` | Convenience helpers for common stage changes. |

### Stability Notes

The filesystem registry is the local source of truth for model manifests.
Approved manifests require approver metadata. Runtime approved-only loading is
an opt-in policy so research and fixture workflows remain backward compatible.

## 9. RiskRule

### Purpose

Evaluate one risk condition.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `name` | none | string | Stable rule name. |
| `evaluate` | trade intent, portfolio snapshot, market context, risk config | rule decision | Approve, reject, or modify. |

### Error Behavior

- Rule configuration errors should fail at initialization.
- Runtime rule failure should reject the intent or raise controlled risk error based on severity.

## 10. PositionSizer

### Purpose

Determine order size after signal intent and before execution.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `size` | signal/trade intent, portfolio snapshot, market context, risk config | sized `TradeIntent` or quantity | Applies sizing policy. |

### Expected Policies

- fixed quantity,
- fixed dollar,
- percent of equity,
- volatility-adjusted,
- risk-per-trade.

## 11. RiskEngine

### Purpose

Aggregate risk rules and sizing decisions.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `evaluate` | signal/target/trade intent, portfolio snapshot, market context | `RiskDecision` | Main risk decision. |
| `evaluate_many` | list of intents, portfolio snapshot, market context | list of `RiskDecision` | Batch processing. |
| `reset_daily_state` | trading date | none | Resets daily loss/cooldown state. |
| `update_after_fill` | `Fill`, portfolio snapshot | none | Updates cooldown/daily risk state. |

### Output Contract

`RiskDecision` must include:

- decision status,
- approved or modified trade intent if approved,
- rejection or modification reasons,
- risk rule results,
- sizing result.

Risk rules use explicit operational semantics: trading-session open is
inclusive and close is exclusive, daily loss includes realized plus unrealized
PnL, and cooldown state is scoped by `(strategy_id, symbol)`.

## 12. ExecutionEngine

### Purpose

Convert approved risk decisions into orders and process order/fill events.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `submit` | `RiskDecision` | `Order` or submission result | Builds and routes order request. |
| `submit_many` | list of `RiskDecision` | list of results | Batch submission. |
| `on_order_update` | `Order` | none | Updates order manager. |
| `on_fill` | `Fill` | none | Handles fill and notifies portfolio/strategy as configured. |
| `on_broker_event` | `BrokerEvent` | none | Applies normalized broker lifecycle events idempotently. |
| `cancel_order` | order ID | cancel result | Delegates to router/broker. |

Order request construction must produce exactly one sizing field: `quantity` or
`notional`, never both. Notional order requests require a runtime execution
policy that permits fractional/notional behavior; whole-share-only runtime
configs must use quantity-based sizing before broker payload generation.

### Ownership Rules

- Execution engine does not decide strategy direction.
- Execution engine does not perform core risk approval.
- Execution engine does not call vendor clients directly.
- Execution engine must enforce configured execution policy such as
  `allow_fractional` before routing normalized order requests.
- Execution engine must skip duplicate broker event IDs and duplicate fill IDs.
- Stale order updates must not regress tracked order status or filled quantity.

## 13. OrderManager

### Purpose

Track normalized order lifecycle.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `register_order` | `Order` | none | Add new order. |
| `update_order` | `Order` | none | Update status and quantities. |
| `get_order` | order ID | optional `Order` | Retrieve tracked order. |
| `list_open_orders` | optional symbol | list of `Order` | Open orders only. |
| `mark_filled` | order ID, `Fill` | updated `Order` | Update filled quantity/status. |
| `mark_canceled` | order ID | updated `Order` | Mark canceled. |

## 14. OrderRouter

### Purpose

Route normalized order requests to the configured brokerage implementation.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `submit_order` | `OrderRequest` | `Order` | Calls brokerage. |
| `cancel_order` | order ID | cancel result | Calls brokerage. |
| `get_order` | order ID | optional `Order` | Calls brokerage or manager. |
| `poll_updates` | since timestamp | list of `Fill` | Backward-compatible fill polling helper. |
| `poll_events` | since timestamp, include order updates | list of `BrokerEvent` | Polling fallback that normalizes broker order and fill updates. |

### Ownership Rules

- Router only depends on `Brokerage` interface.
- Router must not know Alpaca-, IBKR-, or other vendor-specific details.

## 15. Brokerage

### Purpose

Normalize broker behavior across backtesting, paper trading, and live trading.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `connect` | broker config | none | Initialize broker connection. |
| `disconnect` | none | none | Close connection. |
| `submit_order` | `OrderRequest` | `Order` | Submit normalized order. |
| `cancel_order` | order ID | cancel result | Cancel order if possible. |
| `get_order` | order ID | optional `Order` | Retrieve normalized order. |
| `list_orders` | status filter, symbol | list of `Order` | Broker order state. Broad `all`, `open`, and `closed` filters should be supported when practical. |
| `get_account` | none | `Account` | Broker-side account snapshot. |
| `get_positions` | none | list of `Position` | Broker-side positions. |
| `poll_fills` | since timestamp | list of `Fill` | Polling fill updates if streaming unavailable. |
| `is_market_open` | timestamp | bool | Broker/session view if supported. |

### Error Behavior

- Broker rejections return rejected `Order` or raise controlled broker rejection error.
- Connection failures raise broker connection error.
- Vendor exceptions must be converted to internal error types.
- Vendor-specific order confirmation prompts that require manual approval must
  fail closed unless a future phase explicitly designs and tests confirmation
  behavior.
- Polling brokers should expose enough order/fill state for
  `OrderRouter.poll_events()` to build normalized `BrokerEvent` objects.

### Implementations

- `BacktestBrokerage` simulates broker behavior for backtests.
- `AlpacaBrokerage` supports Alpaca paper trading and explicitly gated Alpaca
  live adapter construction behind the D1 submission gates.
- `IBKRBrokerage` supports IBKR paper trading and requires an account ID plus
  symbol-to-`conid` mapping for order submission. IBKR live remains
  fail-closed.

## 15a. BrokerEventSource and Synchronization

### Purpose

Normalize broker push-style lifecycle payloads before they reach execution or
engines, then synchronize those events through deterministic idempotency,
ordering, gap, and restart-checkpoint rules.

### Required Interfaces

| Interface | Inputs | Output | Notes |
|---|---|---|---|
| `BrokerEventSource.iter_events` | none | iterator of `BrokerEvent` | Source may be finite, mocked, or future streaming. |
| `BrokerEventSource.close` | none | none | Releases client resources. |
| `BrokerEventSyncLoop.run` | optional `max_events` | `BrokerEventSyncResult` | Dispatches broker events after duplicate, ordering, and gap checks. |
| `BrokerEventSyncCheckpoint` | last timestamp, processed event IDs | checkpoint state | Used by engines to resume in-process sync without reprocessing event IDs. |
| `BrokerEventSyncPolicy` | dedupe/order/gap settings | policy object | Configures fail-closed behavior for sync. |
| `AlpacaBrokerEventClient.connect` | channels | none | Adapter boundary for Alpaca trade updates. |
| `AlpacaBrokerEventClient.iter_messages` | none | raw Alpaca-shaped payloads | Must not leak beyond integration adapter. |
| `AlpacaBrokerEventSource.iter_events` | none | iterator of `BrokerEvent` | Normalizes Alpaca trade updates. |
| `IBKRBrokerEventClient.connect` | account ID | none | Adapter boundary for IBKR order updates. |
| `IBKRBrokerEventClient.iter_messages` | none | raw IBKR-shaped payloads | Must not leak beyond integration adapter. |
| `IBKRBrokerEventSource.iter_events` | none | iterator of `BrokerEvent` | Normalizes IBKR order updates. |

### Validation Contract

- Vendor error payloads fail closed with controlled data errors.
- Vendor order/fill payloads must be converted to normalized `Order`, `Fill`,
  and `BrokerEvent` objects before leaving `integrations/`.
- Duplicate broker events are skipped when checkpoint deduplication is enabled.
- Out-of-order broker events fail closed unless explicitly configured to skip.
- Optional timestamp gap checks can fail closed before dispatching the next
  broker event.
- Event sources must be closed when a sync run ends or fails.
- Paper/live engine sync methods should reconcile before and after consuming an
  event source.
- In-memory clients remain the only implemented broker-event clients through
  Phase C3; real network transports must be added behind the same protocols
  later.
- Phase C3 adds engine sync plumbing, but persistent checkpoints and real
  network transports remain future work.

## 16. BacktestBrokerage

### Purpose

Simulate brokerage behavior in backtests while implementing the same `Brokerage` interface.

### Additional Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `on_market_event` | `Bar`, `Quote`, or `Trade` | list of `Fill` | Uses current event to simulate fills. |
| `set_fill_model` | fill model config/object | none | Configure fill behavior. |
| `set_commission_model` | commission model | none | Configure costs. |
| `set_slippage_model` | slippage model | none | Configure slippage. |
| `reset` | starting account | none | Reset broker state for new backtest. |

### Fill Policy Contract

Backtest fill policy must be explicit in configuration. Valid initial policies:

- `next_bar_open`
- `next_bar_close`
- `next_bar_typical_price`
- `quote_bid_ask`

Market orders should not fill using the same bar close when the decision was generated from that bar close unless explicitly configured for research-only approximation.

## 17. Portfolio

### Purpose

Track internal portfolio state and accounting.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `initialize` | starting cash, base currency | none | Set initial state. |
| `apply_fill` | `Fill` | updated position/account state | Updates cash and positions. |
| `mark_to_market` | latest prices by symbol, timestamp | `PortfolioSnapshot` | Updates unrealized PnL/equity. |
| `get_position` | symbol | optional `Position` | Current internal position. |
| `get_account_snapshot` | none | `Account` or `PortfolioSnapshot` | Current internal state. |
| `get_trade_ledger` | filters | list of `TradeLedgerEntry` | Historical trades. |
| `get_cash_ledger` | filters | list of `CashLedgerEntry` | Cash movements. |
| `reconcile` | broker account, broker positions | reconciliation result | Paper/live only. |

### Ownership Rules

- Portfolio updates only from fills, cash events, corporate actions, and explicit reconciliation.
- Strategies may read snapshots but may not mutate portfolio.

## 18. BacktestEngine

### Purpose

Run an end-to-end backtest.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `initialize` | runtime config | none | Wire dependencies. |
| `run` | none | `BacktestResult` | Execute full backtest. |
| `step` | optional market event | step result | Optional for debugging. |
| `finalize` | none | `BacktestResult` | Generate final outputs. |

### Expected Call Sequence

1. load config,
2. create providers and clock,
3. initialize portfolio, strategy, risk, execution, brokerage,
4. iterate market data,
5. generate signals,
6. evaluate risk,
7. submit orders,
8. simulate fills,
9. update portfolio,
10. record metrics and report.

## 19. Runtime Market Event Loop

### Purpose

Consume normalized market events from a runtime event source and dispatch them
through paper/live engine callbacks after safety checks.

### Required Interfaces

| Interface | Inputs | Output | Notes |
|---|---|---|---|
| `MarketEventSource.iter_events` | none | iterator of `Bar`/`Quote` | Source may be finite or streaming. |
| `MarketEventSource.close` | none | none | Must release provider resources. |
| `RuntimeEventLoop.run` | optional `max_events` | `RuntimeEventLoopResult` | Dispatches events after validation. |
| `AlpacaStreamClient.connect` | symbols, event types, feed | none | Adapter boundary for Alpaca stream clients. |
| `AlpacaStreamClient.iter_messages` | none | raw Alpaca payload mappings | Must not leak beyond market data adapter. |
| `AlpacaStreamEventSource.iter_events` | none | iterator of `Bar`/`Quote` | Normalizes Alpaca stream payloads. |
| `BrokerEvent` | normalized order/fill/account/position payload | broker lifecycle event | Used by polling fallback and future broker streams. |
| `BrokerEventSource` | none | iterator of `BrokerEvent` | Used by mockable broker push adapters. |

### Validation Contract

- Duplicate events are skipped when deduplication is enabled.
- Per-symbol timestamps must not move backward when fail-closed ordering is
  enabled.
- Optional freshness checks compare event timestamps with the runtime clock.
- Optional heartbeat/data-gap checks compare consecutive dispatched event
  timestamps.
- Optional session filtering uses `MarketSessionService`.
- Provider-specific streaming adapters must convert vendor payloads to internal
  `Bar`/`Quote` models before yielding events.
- Real stream transports must fail closed on provider error payloads or missing
  transport implementation.
- Controlled stream disconnects raise `StreamDisconnectedError`; reconnects
  require an explicit source factory and bounded retry policy.

## 20. LiveEngine

### Purpose

Orchestrate paper or live trading runtime.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `initialize` | runtime config | none | Wire live dependencies. |
| `start` | none | none | Start event loop. |
| `stop` | reason | none | Graceful shutdown. |
| `on_market_event` | event | health/status with decision previews | Handle incoming data, decision previews, and gated automated submission. |
| `on_broker_event` | broker event or order/fill/account event | none | Handle broker updates. |
| `sync_broker_events` | `BrokerEventSource`, optional limits/policy | sync status dict | Checkpointed broker lifecycle sync with reconciliation before/after. |
| `submit_live_order` | `OrderRequest`, optional price | submission status dict | Manual Phase D1 submission path reused by D3 automation after explicit live safety and reconciliation gates. |
| `health_check` | none | health status | Used by monitoring. |

### Safety Contract

Live mode must fail initialization unless explicit live-trading safety flags are enabled.
Dry-run live market events may generate decision previews, but they must not
call broker order submission. Non-dry-run live market events may submit only
when the D3 automation gates pass. Any would-be order must be represented as a
serialized `OrderRequest` preview and validated through live safety gates.
Manual live order submission is a separate Phase D1 path. It requires
non-dry-run live mode, `confirm_live_trading=true`,
`enable_order_submission=true`, a live broker config, account allowlist,
market-session validation, order safety caps, and a matched reconciliation
check immediately before calling `broker.submit_order`.
Phase D2 permits `LiveEngine` to construct the selected Alpaca live brokerage
adapter only after those explicit live submission gates pass. Phase D3 permits
safety-approved live decision previews to submit through the D1 path only when
`enable_automated_submission=true` and
`automated_submission_kill_switch` is not true. The live engine must be
running before automation submits. Automated submission failures or post-submit
reconciliation mismatches must stop further automation and surface critical live
health.

## 21. Reporter

### Purpose

Generate metrics, plots, and exports.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `generate_metrics` | portfolio snapshots, trades, config | metrics object/dict | Performance metrics. |
| `generate_plots` | backtest result, output path | plot files | Optional static SVG equity/drawdown diagnostics with trade markers. |
| `export_report` | backtest result, output path, format | report path | Markdown/JSON/CSV/SVG as configured. |
| `summarize` | result | text/table summary | CLI/chat-friendly summary. |

### Error Behavior

- Missing snapshots should return clear report error.
- Plot failures should be captured as warnings and should not corrupt metric,
  ledger, config, equity-curve CSV, or summary exports.

## 22. Monitoring and Live Safety

### Purpose

Provide operational visibility and guarded live-readiness checks without
enabling unsafe broker submission.

### Required Helpers

| Helper | Inputs | Output | Notes |
|---|---|---|---|
| `HealthCheck` | none | `HealthCheckResult` | One runtime health check. |
| `HealthMonitor` | list of checks | health summary | Aggregates OK/WARNING/CRITICAL checks. |
| `RuntimeMetricsLogger` | metric name, value, tags | metric sample | Records runtime metrics and optional JSONL output. |
| `AlertManager` | severity, source, message, details | alert event | Fans out alerts to configured sinks. |
| `BrokerReconciliationCheck` | portfolio, brokerage | health result | Calls portfolio reconciliation and reports mismatch. |
| `validate_live_safety_config` | `RuntimeConfig` | safety policy | Fails closed unless live gates are explicit. |
| `validate_live_order_submission_config` | `RuntimeConfig` | safety policy | Requires explicit non-dry-run submission gates before `broker.submit_order`. |
| `validate_live_automated_submission_config` | `RuntimeConfig` | safety policy | Requires D1 submission gates plus automated gate and open kill switch. |
| `validate_live_account` | config, broker account | bool | Enforces account allowlists. |
| `validate_order_request_safety` | config, order request, optional price | bool | Enforces symbol and max order size caps. |

### LiveEngine Safety Contract

- `LiveEngine` must require `RuntimeMode.LIVE`.
- Initialization must fail unless `broker.safety.live_enabled` is true.
- Symbol allowlists, account allowlists, and max order size caps must be
  configured before initialization.
- Non-dry-run live mode must require an additional explicit confirmation flag.
- Dry-run initialization must not submit orders or call external broker APIs.
- Manual live order submission additionally requires
  `broker.safety.enable_order_submission=true`.
- Automated strategy-driven live broker submission additionally requires
  `broker.safety.enable_automated_submission=true` and
  `broker.safety.automated_submission_kill_switch` not true.
- Automated submission failures must stop future automated submissions until
  the process/configuration is reset.

### Error Behavior

- Failed safety gates raise a controlled live-safety error.
- Reconciliation mismatches raise a controlled reconciliation error during
  guarded live initialization.
- Critical runtime failures should emit alerts and stop the engine when a
  recovery manager is configured.
