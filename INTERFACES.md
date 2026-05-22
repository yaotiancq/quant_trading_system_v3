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
| `MarketDataProvider` | `market_data/` | local, replay, live providers | engines, data portal |
| `DataPortal` | `market_data/` | default data portal | strategies, features, engines |
| `Indicator` | `features/` | indicator classes/functions | feature pipeline |
| `FeaturePipeline` | `features/` | concrete pipelines | strategies, ML, engines |
| `Strategy` | `strategies/` | rule-based and ML strategies | engines |
| `MLModelInference` | `ml/` | model inference adapters | ML strategies |
| `RiskRule` | `risk/` | concrete risk rules | risk engine |
| `RiskEngine` | `risk/` | default risk engine | engines |
| `PositionSizer` | `risk/` | sizing models | risk engine |
| `ExecutionEngine` | `execution/` | default execution engine | engines |
| `OrderManager` | `execution/` | default order manager | execution engine |
| `OrderRouter` | `execution/` | default order router | execution engine |
| `Brokerage` | `brokers/` | backtest, Alpaca | order router, engines |
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

### Error Behavior

- Missing required columns: raise data validation error.
- Unsupported timeframe: raise configuration or data provider error.
- Provider unavailable: raise provider connection error or return explicit failure result depending on runtime mode.

### Stability Notes

The interface is stable. New providers must conform to it rather than forcing changes upstream.

## 4. DataPortal

### Purpose

Provide a unified read interface to market data and features for strategies and engines.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `get_bars` | symbol, lookback/window, end timestamp | sequence/table of `Bar` | Used by strategies and feature pipelines. |
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
| `load_model` | model URI or registry ID | loaded model handle | Reads registered model. |
| `predict` | `FeatureRecord` or `FeatureFrame` | `ModelPrediction` or list | Runtime prediction. |
| `get_expected_schema` | none | feature schema | Used before prediction. |
| `get_model_metadata` | none | metadata | Model version, training range, metrics. |

### Ownership Rules

- This interface only performs inference.
- It does not submit orders.
- It does not decide final position size unless the strategy explicitly interprets prediction that way and risk approves it.

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
| `cancel_order` | order ID | cancel result | Delegates to router/broker. |

### Ownership Rules

- Execution engine does not decide strategy direction.
- Execution engine does not perform core risk approval.
- Execution engine does not call vendor clients directly.

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
| `poll_updates` | none | order/fill updates | Optional for polling brokers. |

### Ownership Rules

- Router only depends on `Brokerage` interface.
- Router must not know Alpaca-specific details.

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
| `list_orders` | status filter, symbol | list of `Order` | Broker order state. |
| `get_account` | none | `Account` | Broker-side account snapshot. |
| `get_positions` | none | list of `Position` | Broker-side positions. |
| `poll_fills` | since timestamp | list of `Fill` | Polling fill updates if streaming unavailable. |
| `is_market_open` | timestamp | bool | Broker/session view if supported. |

### Error Behavior

- Broker rejections return rejected `Order` or raise controlled broker rejection error.
- Connection failures raise broker connection error.
- Vendor exceptions must be converted to internal error types.

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

## 19. LiveEngine

### Purpose

Orchestrate paper or live trading runtime.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `initialize` | runtime config | none | Wire live dependencies. |
| `start` | none | none | Start event loop. |
| `stop` | reason | none | Graceful shutdown. |
| `on_market_event` | event | none | Handle incoming data. |
| `on_broker_event` | order/fill/account event | none | Handle broker updates. |
| `health_check` | none | health status | Used by monitoring. |

### Safety Contract

Live mode must fail initialization unless explicit live-trading safety flags are enabled.

## 20. Reporter

### Purpose

Generate metrics, plots, and exports.

### Required Methods

| Method | Inputs | Output | Notes |
|---|---|---|---|
| `generate_metrics` | portfolio snapshots, trades, config | metrics object/dict | Performance metrics. |
| `generate_plots` | backtest result, output path | plot files | Equity/drawdown/trade markers. |
| `export_report` | backtest result, output path, format | report path | Markdown/HTML/CSV as configured. |
| `summarize` | result | text/table summary | CLI/chat-friendly summary. |

### Error Behavior

- Missing snapshots should return clear report error.
- Plot failures should not corrupt metric exports.

## 21. Monitoring and Live Safety

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
| `validate_live_account` | config, broker account | bool | Enforces account allowlists. |
| `validate_order_request_safety` | config, order request, optional price | bool | Enforces symbol and max order size caps. |

### LiveEngine Safety Contract

- `LiveEngine` must require `RuntimeMode.LIVE`.
- Initialization must fail unless `broker.safety.live_enabled` is true.
- Symbol allowlists, account allowlists, and max order size caps must be
  configured before initialization.
- Non-dry-run live mode must require an additional explicit confirmation flag.
- Phase 8 dry-run initialization must not submit orders or call external broker
  APIs.
- Real live broker submission remains disabled until a later documented phase.

### Error Behavior

- Failed safety gates raise a controlled live-safety error.
- Reconciliation mismatches raise a controlled reconciliation error during
  guarded live initialization.
- Critical runtime failures should emit alerts and stop the engine when a
  recovery manager is configured.
