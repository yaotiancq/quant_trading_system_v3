# DATA_MODELS.md

# Core Data Models

## 1. Global Conventions

- Timestamps must be timezone-aware.
- Internal timestamps should be normalized to UTC.
- Symbols should be uppercase US equity symbols unless future symbol mapping states otherwise.
- Monetary values should use fixed-precision decimal or carefully controlled float representation.
- Vendor-specific API objects must be converted into these internal models at adapter boundaries.
- Model fields may be implemented using dataclasses, Pydantic models, or another validated Python model system.

## 2. Common Enums

| Enum | Values |
|---|---|
| `RuntimeMode` | `BACKTEST`, `PAPER`, `LIVE` |
| `AssetClass` | `EQUITY`, `ETF`, `CRYPTO`, `OPTION`, `FUTURE` |
| `BarTimeframe` | `SECOND`, `MINUTE`, `HOUR`, `DAY` |
| `SignalDirection` | `BUY`, `SELL`, `SHORT`, `COVER`, `HOLD`, `EXIT` |
| `OrderSide` | `BUY`, `SELL` |
| `OrderType` | `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT` |
| `OrderStatus` | `NEW`, `ACCEPTED`, `REJECTED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED`, `EXPIRED`, `FAILED` |
| `TimeInForce` | `DAY`, `GTC`, `IOC`, `FOK` |
| `RiskDecisionStatus` | `APPROVED`, `REJECTED`, `MODIFIED` |
| `DataAdjustment` | `RAW`, `SPLIT_ADJUSTED`, `DIVIDEND_ADJUSTED`, `TOTAL_RETURN` |
| `BrokerEventType` | `ORDER_UPDATE`, `FILL`, `ACCOUNT_UPDATE`, `POSITION_UPDATE` |

---

## 2a. MarketSession

### Purpose

Represents one resolved exchange session with UTC-normalized boundaries.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `exchange` | string | yes | supported exchange code such as `XNYS` or `NASDAQ` |
| `session_date` | date | yes | local exchange session date |
| `timezone` | string | yes | valid IANA timezone |
| `regular_open` | datetime | yes | timezone-aware UTC |
| `regular_close` | datetime | yes | timezone-aware UTC, exclusive |
| `premarket_open` | datetime | no | UTC, only when extended hours are enabled |
| `after_hours_close` | datetime | no | UTC, only when extended hours are enabled |
| `early_close` | bool | yes | true for shortened regular sessions |
| `metadata` | dict | no | provider details |

### Validation Rules

- Regular open is inclusive.
- Regular close is exclusive.
- Tradable open/close may include extended-hours windows when configured.
- A missing session means the exchange is closed or the calendar failed closed.

### Producers

- calendar/session service.

### Consumers

- market data download filters,
- runtime engines,
- monitoring and live safety,
- broker `is_market_open` fallbacks.

---

## 3. Bar

### Purpose

Represents one OHLCV market bar.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbol` | string | yes | uppercase, non-empty |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `timeframe` | enum/string | yes | supported timeframe |
| `open` | decimal/float | yes | non-negative |
| `high` | decimal/float | yes | `high >= max(open, close, low)` |
| `low` | decimal/float | yes | `low <= min(open, close, high)` |
| `close` | decimal/float | yes | non-negative |
| `volume` | int/float | yes | non-negative |
| `vwap` | decimal/float | no | non-negative if present |
| `trade_count` | int | no | non-negative |
| `source` | string | no | provider name |

### Example

```json
{
  "symbol": "SPY",
  "timestamp": "2026-01-05T14:31:00Z",
  "timeframe": "MINUTE",
  "open": 500.10,
  "high": 500.35,
  "low": 499.95,
  "close": 500.20,
  "volume": 125000,
  "vwap": 500.18,
  "source": "local_parquet"
}
```

### Producers

- market data providers,
- replay provider,
- vendor adapters.

### Consumers

- feature pipeline,
- strategies,
- backtest brokerage,
- portfolio mark-to-market,
- reporting.

---

## 4. Quote

### Purpose

Represents bid/ask market quote.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `bid_price` | decimal/float | yes | non-negative |
| `bid_size` | int/float | no | non-negative |
| `ask_price` | decimal/float | yes | non-negative, ask >= bid under normal conditions |
| `ask_size` | int/float | no | non-negative |
| `source` | string | no | provider name |

### Example

```json
{
  "symbol": "AAPL",
  "timestamp": "2026-01-05T14:31:02Z",
  "bid_price": 190.12,
  "bid_size": 200,
  "ask_price": 190.14,
  "ask_size": 300,
  "source": "alpaca"
}
```

### Producers

- live market data providers,
- historical quote providers.

### Consumers

- quote-aware fill models,
- strategies,
- execution checks,
- monitoring.

---

## 5. Trade

### Purpose

Represents an executed market trade print.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `price` | decimal/float | yes | positive |
| `size` | int/float | yes | positive |
| `exchange` | string | no | optional |
| `conditions` | list[string] | no | optional |
| `source` | string | no | provider name |

### Example

```json
{
  "symbol": "MSFT",
  "timestamp": "2026-01-05T14:31:02Z",
  "price": 430.25,
  "size": 100,
  "exchange": "NASDAQ"
}
```

### Producers

- trade data providers.

### Consumers

- advanced features,
- future tick/second-level engines,
- reporting.

---

## 6. Signal

### Purpose

Strategy-level directional view before sizing and risk approval.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `signal_id` | string | yes | unique within run |
| `strategy_id` | string | yes | non-empty |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `direction` | `SignalDirection` | yes | valid enum |
| `strength` | float | no | recommended range `[-1.0, 1.0]` |
| `confidence` | float | no | range `[0.0, 1.0]` |
| `reason` | string | no | human-readable reason |
| `metadata` | dict | no | serializable |

### Example

```json
{
  "signal_id": "sig-001",
  "strategy_id": "sma_cross_v1",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:00:00Z",
  "direction": "BUY",
  "strength": 0.8,
  "confidence": 0.7,
  "reason": "fast_sma_crossed_above_slow_sma"
}
```

### Producers

- strategies.

### Consumers

- risk engine,
- reporting,
- research.

---

## 7. TargetPosition

### Purpose

Represents desired final exposure for a symbol.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `target_id` | string | yes | unique within run |
| `strategy_id` | string | yes | non-empty |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `target_quantity` | decimal/float | no | may be positive, zero, or negative if shorts later supported |
| `target_weight` | float | no | typically `[-1.0, 1.0]` |
| `target_notional` | decimal/float | no | non-negative absolute target |
| `reason` | string | no | optional |
| `metadata` | dict | no | serializable |

### Validation Rules

At least one of `target_quantity`, `target_weight`, or `target_notional` must be provided.

### Example

```json
{
  "target_id": "tp-001",
  "strategy_id": "portfolio_rotation_v1",
  "symbol": "QQQ",
  "timestamp": "2026-01-05T15:00:00Z",
  "target_weight": 0.25,
  "reason": "ranked_top_bucket"
}
```

### Producers

- strategies,
- portfolio construction modules.

### Consumers

- risk engine,
- position sizer.

---

## 8. TradeIntent

### Purpose

Represents a strategy's requested trade before final risk approval and order conversion.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `intent_id` | string | yes | unique within run |
| `strategy_id` | string | yes | non-empty |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `side` | `OrderSide` | yes | valid enum |
| `quantity` | decimal/float | no | positive if provided |
| `notional` | decimal/float | no | positive if provided |
| `order_type` | `OrderType` | yes | default may be `MARKET` |
| `limit_price` | decimal/float | no | required for limit orders |
| `stop_price` | decimal/float | no | required for stop orders |
| `time_in_force` | `TimeInForce` | yes | default `DAY` |
| `source_signal_id` | string | no | link to signal |
| `reason` | string | no | optional |
| `metadata` | dict | no | serializable |

### Validation Rules

- `quantity` and `notional` are mutually exclusive.
- An unsized intent may omit both fields before risk sizing.
- Exactly one of `quantity` or `notional` must be present before order
  submission.
- `limit_price` is required for `LIMIT` and `STOP_LIMIT`.
- `stop_price` is required for `STOP` and `STOP_LIMIT`.

### Example

```json
{
  "intent_id": "intent-001",
  "strategy_id": "sma_cross_v1",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:00:00Z",
  "side": "BUY",
  "quantity": 10,
  "order_type": "MARKET",
  "time_in_force": "DAY",
  "source_signal_id": "sig-001"
}
```

### Producers

- strategies,
- risk position sizer when converting signals.

### Consumers

- risk engine,
- execution engine.

---

## 9. RiskDecision

### Purpose

Result of risk evaluation.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `decision_id` | string | yes | unique |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `status` | `RiskDecisionStatus` | yes | valid enum |
| `original_intent` | `TradeIntent` | yes | original request |
| `approved_intent` | `TradeIntent` | no | required if approved/modified |
| `reasons` | list[string] | yes | non-empty for rejection/modification |
| `rule_results` | list[dict] | no | per-rule details |
| `sizing_details` | dict | no | sizing metadata |

### Example

```json
{
  "decision_id": "risk-001",
  "timestamp": "2026-01-05T15:00:01Z",
  "status": "APPROVED",
  "original_intent": "intent-001",
  "approved_intent": "intent-001-sized",
  "reasons": ["within_position_limit", "buying_power_ok"]
}
```

### Producers

- risk engine.

### Consumers

- execution engine,
- reporting,
- monitoring.

---

## 10. OrderRequest

### Purpose

Normalized order request ready for brokerage submission.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `client_order_id` | string | yes | unique idempotency key |
| `strategy_id` | string | no | optional attribution |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `side` | `OrderSide` | yes | valid enum |
| `quantity` | decimal/float | no | positive |
| `notional` | decimal/float | no | positive |
| `order_type` | `OrderType` | yes | valid enum |
| `limit_price` | decimal/float | no | required for limit orders |
| `stop_price` | decimal/float | no | required for stop orders |
| `time_in_force` | `TimeInForce` | yes | valid enum |
| `metadata` | dict | no | serializable |

### Validation Rules

- Exactly one of `quantity` or `notional` must be present.
- Quantity and notional order semantics are mutually exclusive.
- All broker-required fields must be complete before adapter mapping.
- `limit_price` is required for `LIMIT` and `STOP_LIMIT`.
- `stop_price` is required for `STOP` and `STOP_LIMIT`.

### Example

```json
{
  "client_order_id": "coid-20260105-0001",
  "strategy_id": "sma_cross_v1",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:00:01Z",
  "side": "BUY",
  "quantity": 10,
  "order_type": "MARKET",
  "time_in_force": "DAY"
}
```

### Producers

- execution engine.

### Consumers

- brokerage adapters.

---

## 11. Order

### Purpose

Normalized broker order state.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `order_id` | string | yes | broker/internal order ID |
| `client_order_id` | string | yes | idempotency key |
| `symbol` | string | yes | uppercase |
| `created_at` | datetime | yes | timezone-aware UTC |
| `updated_at` | datetime | no | timezone-aware UTC |
| `side` | `OrderSide` | yes | valid enum |
| `quantity` | decimal/float | no | positive |
| `filled_quantity` | decimal/float | yes | non-negative |
| `remaining_quantity` | decimal/float | no | non-negative |
| `order_type` | `OrderType` | yes | valid enum |
| `status` | `OrderStatus` | yes | valid enum |
| `limit_price` | decimal/float | no | optional |
| `stop_price` | decimal/float | no | optional |
| `average_fill_price` | decimal/float | no | non-negative |
| `rejection_reason` | string | no | required if rejected |
| `metadata` | dict | no | serializable |

### Example

```json
{
  "order_id": "bt-order-001",
  "client_order_id": "coid-20260105-0001",
  "symbol": "SPY",
  "created_at": "2026-01-05T15:00:01Z",
  "side": "BUY",
  "quantity": 10,
  "filled_quantity": 10,
  "remaining_quantity": 0,
  "order_type": "MARKET",
  "status": "FILLED",
  "average_fill_price": 500.25
}
```

### Producers

- brokerage adapters,
- order manager.

### Consumers

- execution engine,
- portfolio,
- reporting.

---

## 12. Fill

### Purpose

Represents full or partial execution of an order.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `fill_id` | string | yes | unique |
| `order_id` | string | yes | existing order |
| `client_order_id` | string | no | optional link |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `side` | `OrderSide` | yes | valid enum |
| `quantity` | decimal/float | yes | positive |
| `price` | decimal/float | yes | positive |
| `commission` | decimal/float | yes | non-negative |
| `slippage` | decimal/float | no | optional |
| `liquidity_flag` | string | no | optional |
| `source` | string | yes | `backtest`, `alpaca_paper`, etc. |

### Example

```json
{
  "fill_id": "fill-001",
  "order_id": "bt-order-001",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:01:00Z",
  "side": "BUY",
  "quantity": 10,
  "price": 500.25,
  "commission": 0.00,
  "source": "backtest"
}
```

### Producers

- brokerage adapters.

### Consumers

- execution engine,
- portfolio,
- strategies,
- reporting,
- monitoring.

---

## 13. Position

### Purpose

Represents current holding for one symbol.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbol` | string | yes | uppercase |
| `quantity` | decimal/float | yes | may be zero |
| `average_cost` | decimal/float | yes | non-negative |
| `market_price` | decimal/float | no | non-negative |
| `market_value` | decimal/float | no | computed |
| `unrealized_pnl` | decimal/float | no | computed |
| `realized_pnl` | decimal/float | no | computed |
| `updated_at` | datetime | yes | timezone-aware UTC |

### Example

```json
{
  "symbol": "SPY",
  "quantity": 10,
  "average_cost": 500.25,
  "market_price": 501.00,
  "market_value": 5010.00,
  "unrealized_pnl": 7.50,
  "realized_pnl": 0.00,
  "updated_at": "2026-01-05T16:00:00Z"
}
```

### Producers

- portfolio,
- brokerage adapters for broker-side state.

### Consumers

- risk engine,
- strategies,
- reporting,
- reconciliation.

---

## 14. Account

### Purpose

Represents account-level state.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `account_id` | string | no | broker/internal account ID |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `currency` | string | yes | default `USD` |
| `cash` | decimal/float | yes | may be constrained non-negative |
| `equity` | decimal/float | yes | cash + market value |
| `buying_power` | decimal/float | yes | non-negative |
| `gross_exposure` | decimal/float | no | non-negative |
| `net_exposure` | decimal/float | no | may be negative |
| `realized_pnl` | decimal/float | no | optional |
| `unrealized_pnl` | decimal/float | no | optional |
| `metadata` | dict | no | serializable |

### Example

```json
{
  "account_id": "backtest",
  "timestamp": "2026-01-05T16:00:00Z",
  "currency": "USD",
  "cash": 94997.50,
  "equity": 100007.50,
  "buying_power": 94997.50,
  "gross_exposure": 5010.00,
  "net_exposure": 5010.00
}
```

### Producers

- portfolio,
- brokerage adapters.

### Consumers

- risk engine,
- reporting,
- reconciliation.

---

## 15. PortfolioSnapshot

### Purpose

Point-in-time internal portfolio snapshot.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `timestamp` | datetime | yes | timezone-aware UTC |
| `cash` | decimal/float | yes | account currency |
| `equity` | decimal/float | yes | cash + positions |
| `positions_value` | decimal/float | yes | non-negative absolute market value |
| `realized_pnl` | decimal/float | yes | cumulative |
| `unrealized_pnl` | decimal/float | yes | current |
| `gross_exposure` | decimal/float | yes | non-negative |
| `net_exposure` | decimal/float | yes | signed |
| `positions` | list[`Position`] | yes | current positions |
| `metadata` | dict | no | serializable |

### Example

```json
{
  "timestamp": "2026-01-05T16:00:00Z",
  "cash": 94997.50,
  "equity": 100007.50,
  "positions_value": 5010.00,
  "realized_pnl": 0.00,
  "unrealized_pnl": 7.50,
  "gross_exposure": 5010.00,
  "net_exposure": 5010.00,
  "positions": ["SPY"]
}
```

### Producers

- portfolio.

### Consumers

- risk engine,
- strategies,
- reporting,
- engines.

---

## 16. TradeLedgerEntry

### Purpose

Auditable record of executed trade impact.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `entry_id` | string | yes | unique |
| `fill_id` | string | yes | source fill |
| `order_id` | string | yes | source order |
| `strategy_id` | string | no | attribution |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `side` | `OrderSide` | yes | valid enum |
| `quantity` | decimal/float | yes | positive |
| `price` | decimal/float | yes | positive |
| `commission` | decimal/float | yes | non-negative |
| `realized_pnl_delta` | decimal/float | no | computed |
| `position_quantity_after` | decimal/float | yes | computed |
| `average_cost_after` | decimal/float | yes | computed |

### Example

```json
{
  "entry_id": "tle-001",
  "fill_id": "fill-001",
  "order_id": "bt-order-001",
  "strategy_id": "sma_cross_v1",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:01:00Z",
  "side": "BUY",
  "quantity": 10,
  "price": 500.25,
  "commission": 0.00,
  "position_quantity_after": 10,
  "average_cost_after": 500.25
}
```

### Producers

- portfolio.

### Consumers

- reporting,
- reconciliation,
- audit.

---

## 17. CashLedgerEntry

### Purpose

Auditable record of cash changes.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `entry_id` | string | yes | unique |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `event_type` | string | yes | trade, commission, deposit, withdrawal, dividend |
| `amount` | decimal/float | yes | signed |
| `currency` | string | yes | default `USD` |
| `cash_after` | decimal/float | yes | resulting cash |
| `related_fill_id` | string | no | optional |
| `related_order_id` | string | no | optional |
| `description` | string | no | optional |

### Example

```json
{
  "entry_id": "cle-001",
  "timestamp": "2026-01-05T15:01:00Z",
  "event_type": "trade",
  "amount": -5002.50,
  "currency": "USD",
  "cash_after": 94997.50,
  "related_fill_id": "fill-001"
}
```

### Producers

- portfolio.

### Consumers

- reporting,
- audit,
- reconciliation.

---

## 18. BacktestResult

### Purpose

Final result of a backtest run.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `run_id` | string | yes | unique |
| `config` | `RuntimeConfig` | yes | backtest config |
| `start_time` | datetime | yes | run start |
| `end_time` | datetime | yes | run end |
| `symbols` | list[string] | yes | non-empty |
| `portfolio_snapshots` | list[`PortfolioSnapshot`] | yes | ordered by timestamp |
| `orders` | list[`Order`] | yes | all orders |
| `fills` | list[`Fill`] | yes | all fills |
| `trade_ledger` | list[`TradeLedgerEntry`] | yes | all ledger entries |
| `cash_ledger` | list[`CashLedgerEntry`] | yes | all cash entries |
| `metrics` | dict | yes | performance metrics |
| `artifacts` | dict | no | paths to reports and optional SVG plots |
| `warnings` | list[string] | no | non-fatal issues |

### Example

```json
{
  "run_id": "bt-20260105-001",
  "symbols": ["SPY"],
  "start_time": "2026-01-05T14:30:00Z",
  "end_time": "2026-01-05T21:00:00Z",
  "metrics": {
    "total_return": 0.0012,
    "max_drawdown": -0.0008,
    "trade_count": 2
  }
}
```

### Producers

- backtest engine.

### Consumers

- reporter,
- research,
- scripts.

---

## 19. ModelPrediction

### Purpose

Runtime output from an ML model before strategy interpretation.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `prediction_id` | string | yes | unique |
| `model_id` | string | yes | registered model ID |
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | feature timestamp |
| `prediction_value` | float | yes | model-specific |
| `prediction_label` | string/int | no | optional class label |
| `probability` | float | no | range `[0.0, 1.0]` |
| `horizon` | string | no | prediction horizon |
| `feature_schema_version` | string | yes | must match model metadata |
| `metadata` | dict | no | serializable |

### Example

```json
{
  "prediction_id": "pred-001",
  "model_id": "xgb_direction_v1",
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:00:00Z",
  "prediction_value": 0.63,
  "prediction_label": "UP",
  "probability": 0.63,
  "horizon": "next_5_bars",
  "feature_schema_version": "features_v1"
}
```

### Producers

- ML inference pipeline.

### Consumers

- ML strategy adapter,
- reporting.

---

## 20. MLModelManifest

### Purpose

Portable contract for a saved ML model artifact in the local filesystem
registry.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `manifest_version` | string | yes | current value `ml_model_manifest_v1` |
| `model_id` | string | yes | non-empty registered model ID |
| `model_type` | string | yes | supported model type such as `directional_linear_v1` |
| `model_artifact` | string | yes | model artifact filename such as `model.json` |
| `feature_schema_version` | string | yes | non-empty |
| `feature_names` | list[string] | yes | ordered, non-empty |
| `feature_schema_hash` | string | yes | deterministic hash of schema version and ordered feature names |
| `stage` | string | yes | `candidate`, `validated`, `approved`, `archived`, or `legacy` |
| `metrics` | dict | no | serializable training/evaluation metrics |
| `metadata` | dict | no | serializable training and model metadata |
| `approved_by` | string | no | required when `stage` is `approved` |
| `approved_at` | datetime | no | UTC approval timestamp required when `stage` is `approved` |
| `approval_reason` | string | no | optional approval note |
| `stage_history` | list[dict] | no | append-only local transition history |
| `created_at` | datetime | yes | timezone-aware UTC |

### Validation Rules

- `approved` manifests require `approved_by` and `approved_at`.
- `approved_at` cannot be present without `approved_by`.
- Runtime approval policy may reject any stage outside the configured
  `allowed_model_stages`.

### Producers

- model registry.

### Consumers

- ML inference,
- runtime strategies,
- future model approval and audit workflows.

---

## 21. FeatureFrame / FeatureRecord

### Purpose

Stores computed features for batch or online use.

### FeatureFrame Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbols` | list[string] | yes | non-empty |
| `timestamps` | list[datetime] | yes | ordered |
| `features` | table/frame | yes | schema-valid |
| `schema_version` | string | yes | non-empty |
| `generated_at` | datetime | yes | timezone-aware UTC |
| `source` | string | no | pipeline name |

### FeatureRecord Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `symbol` | string | yes | uppercase |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `values` | dict[string, number] | yes | schema-valid |
| `schema_version` | string | yes | non-empty |

### Example

```json
{
  "symbol": "SPY",
  "timestamp": "2026-01-05T15:00:00Z",
  "values": {
    "sma_20": 499.80,
    "rsi_14": 58.4,
    "ret_1": 0.0008
  },
  "schema_version": "features_v1"
}
```

### Producers

- feature pipeline.

### Consumers

- strategies,
- ML dataset builder,
- ML inference,
- reporting.

---

## 22. StrategyConfig

### Purpose

Configuration for a strategy instance.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `strategy_id` | string | yes | unique |
| `strategy_type` | string | yes | registered strategy type |
| `symbols` | list[string] | yes | non-empty |
| `parameters` | dict | yes | strategy-specific |
| `feature_config` | dict | no | optional feature specs and schema version for runtime feature construction |
| `enabled` | bool | yes | default true |

### Example

```json
{
  "strategy_id": "sma_cross_v1",
  "strategy_type": "sma_crossover",
  "symbols": ["SPY"],
  "parameters": {
    "fast_window": 20,
    "slow_window": 50
  },
  "feature_config": {
    "schema_version": "features_v1",
    "required_features": ["sma_20", "sma_50"]
  },
  "enabled": true
}
```

Runtime engines may also consume `feature_config.specs` entries with
`name` and `parameters` fields when a strategy, such as an ML runtime strategy,
requires an explicit training-serving feature schema.

### Producers

- config loader.

### Consumers

- strategy factory,
- engines.

---

## 23. RiskConfig

### Purpose

Configuration for risk rules and sizing.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `max_position_notional` | decimal/float | no | positive |
| `max_gross_exposure` | decimal/float | no | positive |
| `max_symbol_weight` | float | no | `[0, 1]` |
| `daily_loss_limit` | decimal/float | no | positive |
| `allowed_symbols` | list[string] | no | uppercase |
| `blocked_symbols` | list[string] | no | uppercase |
| `sizing_method` | string | yes | registered method |
| `sizing_parameters` | dict | yes | method-specific |
| `cooldown_seconds` | int | no | non-negative |
| `session_rules` | dict | no | market/session config |
| `disabled_until_configured` | bool | no | explicit guard for incomplete templates |

Risk-rule semantics:

- `daily_loss_limit` is checked against realized plus unrealized PnL.
- `cooldown_seconds` is applied per `(strategy_id, symbol)` path.
- `session_rules.market_open` is inclusive and `market_close` is exclusive.

### Example

```json
{
  "max_position_notional": 10000,
  "max_gross_exposure": 50000,
  "max_symbol_weight": 0.2,
  "sizing_method": "fixed_notional",
  "sizing_parameters": {
    "notional_per_trade": 5000
  },
  "allowed_symbols": ["SPY", "QQQ"]
}
```

### Producers

- config loader.

### Consumers

- risk engine,
- position sizer,
- engines.

---

## 24. BrokerConfig

### Purpose

Configuration for broker implementation.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `broker_type` | string | yes | `backtest`, `alpaca_paper`, `alpaca_live`, `ibkr_paper`, `ibkr_live` |
| `account_id` | string | no | optional |
| `paper` | bool | no | true for paper mode |
| `base_url` | string | no | vendor-specific |
| `credential_env_keys` | dict | no | environment variable names |
| `commission_model` | dict | no | backtest cost config |
| `slippage_model` | dict | no | backtest slippage config |
| `fill_policy` | string | no | backtest fill policy |
| `safety` | dict | no | live safety settings and adapter-specific safe defaults, e.g. `enable_order_submission`, Alpaca live adapter gates, IBKR `symbol_conids` |

### Example

```json
{
  "broker_type": "backtest",
  "commission_model": {"type": "per_share", "value": 0.0},
  "slippage_model": {"type": "bps", "value": 1.0},
  "fill_policy": "next_bar_open"
}
```

### Producers

- config loader.

### Consumers

- broker factory,
- broker adapter safety validation,
- execution engine,
- engines.

---

## 25. RuntimeConfig

### Purpose

Top-level configuration for a run.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `run_id` | string | yes | unique or generated |
| `runtime_mode` | `RuntimeMode` | yes | valid enum |
| `symbols` | list[string] | yes | non-empty |
| `start` | datetime/date | mode-dependent | required for backtest |
| `end` | datetime/date | mode-dependent | required for backtest |
| `timeframe` | `BarTimeframe` | yes | supported |
| `market_data` | dict | yes | provider config |
| `broker` | `BrokerConfig` | yes | broker config |
| `strategies` | list[`StrategyConfig`] | yes | at least one enabled |
| `risk` | `RiskConfig` | yes | risk config |
| `portfolio` | dict | yes | starting cash, currency |
| `execution` | dict | yes | order/execution config, including `allow_fractional` |
| `market_session` | dict | no | exchange/session config for runtime checks |
| `reporting` | dict | no | output config |
| `monitoring` | dict | no | runtime monitoring config |

Active runtime YAML files must explicitly set `runtime.mode`, `symbols`, and
`timeframe`; these operational fields are not inherited from `configs/base.yaml`.
Supported `reporting` keys are `output_dir`, `generate_plots`,
`annualization_factor`, and `risk_free_rate`. When `generate_plots` is true,
backtest report export may add `equity_curve_chart` and `drawdown_chart` SVG
paths to `BacktestResult.artifacts`.
Supported `market_session` keys are `exchange`, `timezone`,
`regular_session_only`, `extended_hours`, `fail_closed`, `calendar_provider`,
`regular_open`, and `regular_close`.
Supported paper `market_data.provider` values are `external_events`,
`fake_stream`, `alpaca_stream`, `alpaca_sip_stream`, and `alpaca_iex_stream`.
For `fake_stream`, `market_data.events` is a list of normalized bar or quote
event mappings. For `alpaca_stream`, `market_data.mock_messages` is an optional
list of Alpaca-shaped stream payloads used by the in-memory stream client;
production websocket transport is still a future phase. Optional keys include
`event_types`, `feed`, `symbols`, `session_filter`, `deduplicate`,
`fail_on_out_of_order`, `max_staleness_seconds`, `reconnect`, and `heartbeat`.
`reconnect` supports `enabled`, `max_attempts`, and `backoff_seconds`.
`heartbeat` supports `timeout_seconds` and `fail_closed`.

### Example

```json
{
  "run_id": "bt-spy-sma-001",
  "runtime_mode": "BACKTEST",
  "symbols": ["SPY"],
  "start": "2024-01-01",
  "end": "2024-12-31",
  "timeframe": "MINUTE",
  "market_data": {"provider": "local_parquet", "path": "data/raw/bars.parquet"},
  "broker": {"broker_type": "backtest", "fill_policy": "next_bar_open"},
  "strategies": ["sma_cross_v1"],
  "risk": {"sizing_method": "fixed_notional"},
  "portfolio": {"starting_cash": 100000, "currency": "USD"}
}
```

### Producers

- config loader.

### Consumers

- engines,
- factories,
- reporters.

---

## 26. RuntimeEventLoopResult

### Purpose

Summary counters returned by one runtime event-loop run.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `processed_count` | int | yes | dispatched event count |
| `skipped_count` | int | yes | duplicate or filtered event count |
| `duplicate_count` | int | yes | duplicate events skipped |
| `disconnect_count` | int | yes | controlled stream disconnects observed |
| `reconnect_count` | int | yes | reconnect attempts performed |
| `heartbeat_miss_count` | int | yes | event heartbeat/data-gap misses |
| `source_run_count` | int | yes | source iterator runs attempted |
| `last_event_timestamp` | datetime/null | no | UTC timestamp of latest dispatched event |
| `closed` | bool | yes | true after the source close hook runs |
| `stopped_reason` | string/null | no | `max_events`, `source_exhausted`, or `stream_disconnected` |
| `errors` | list[string] | yes | controlled error messages captured before re-raise |

### Producers

- `RuntimeEventLoop`.

### Consumers

- paper runtime health/status output,
- tests,
- future live/runtime monitoring.

---

## 27. BrokerEvent

### Purpose

Normalized broker lifecycle event envelope used by polling fallback and future
broker push streams. A broker event carries exactly one normalized domain
payload; vendor-specific payloads must be mapped before this model is created.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `event_id` | string | yes | stable idempotency key for the update |
| `event_type` | `BrokerEventType` | yes | matches the payload field |
| `timestamp` | datetime | yes | timezone-aware UTC |
| `source` | string | yes | broker adapter or event-source name |
| `order` | `Order` | no | required only for `ORDER_UPDATE` |
| `fill` | `Fill` | no | required only for `FILL` |
| `account` | `Account` | no | required only for `ACCOUNT_UPDATE` |
| `position` | `Position` | no | required only for `POSITION_UPDATE` |
| `metadata` | dict | no | serializable event-source details |

### Validation Rules

- Exactly one payload field must be present.
- The payload field must match `event_type`.
- `event_id` is used by runtime synchronization to skip duplicate broker
  events.

### Producers

- execution polling fallback,
- Alpaca broker event stream adapter,
- IBKR broker event stream adapter,
- future broker event stream adapters.

### Consumers

- execution engine,
- paper/live engines,
- future broker-event audit logging.

---

## 28. BrokerEventSyncCheckpoint and BrokerEventSyncResult

### Purpose

Runtime synchronization state for broker-event streams. The checkpoint is
kept by paper/live engines during a process run so duplicate broker events are
not reprocessed after a local restart/resume. The result is exposed in engine
health/status output after a sync run.

### BrokerEventSyncCheckpoint Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `last_event_timestamp` | datetime | no | timezone-aware UTC when present |
| `processed_event_ids` | set[string] | yes | stable broker event IDs already applied |
| `processed_count` | int | yes | non-negative count of processed events |

### BrokerEventSyncResult Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `processed_count` | int | yes | events dispatched to the handler |
| `skipped_count` | int | yes | duplicates or skipped stale events |
| `duplicate_count` | int | yes | event IDs already in checkpoint |
| `gap_count` | int | yes | timestamp gaps detected by policy |
| `out_of_order_count` | int | yes | events older than checkpoint timestamp |
| `last_event_timestamp` | datetime | no | latest processed broker event timestamp |
| `closed` | bool | yes | whether the event source was closed |
| `stopped_reason` | string | no | `max_events`, `source_exhausted`, or error context |
| `errors` | list[string] | yes | controlled error messages captured before re-raise |

### Producers

- `BrokerEventSyncLoop`,
- paper/live engine broker-event sync methods.

### Consumers

- paper/live engine health output,
- tests,
- future operational monitoring.

---

## 29. LiveDecisionPreview

### Purpose

Structured status payload for a live decision preview. In dry-run or
automation-disabled mode it records a would-be order without broker submission.
When D3 automation is explicitly enabled, a safety-approved preview can also
record the resulting broker submission.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `preview_id` | string | yes | derived from risk decision id |
| `timestamp` | datetime string | yes | UTC ISO timestamp |
| `symbol` | string | yes | normalized symbol |
| `risk_decision_id` | string | yes | source risk decision |
| `risk_status` | string | yes | approved, modified, or rejected |
| `preview_status` | string | yes | `safety_approved`, `safety_rejected`, or `risk_rejected` |
| `would_submit` | bool | yes | true only when risk and safety allow the order |
| `reasons` | list[string] | yes | sizing/risk reasons |
| `order_request` | dict/null | no | serialized normalized order request |
| `error` | string/null | no | safety or order-request error |
| `automation_status` | string | yes | `not_applicable`, `disabled`, `blocked`, `submitted`, or `failed` |
| `automation_error` | string/null | no | automated submission gate or failure reason |
| `submission_result` | dict/null | no | serialized `LiveOrderSubmissionResult` when automation submits |
| `post_submission_reconciliation` | dict/null | no | reconciliation payload after automated submission |

### Producers

- guarded dry-run `LiveEngine`.
- D3 automated live decision submission.

### Consumers

- live health/status output,
- tests,
- future audit logging.

---

## 30. LiveOrderSubmissionResult

### Purpose

Structured status payload emitted by `LiveEngine.submit_live_order(...)` after
a manually supplied live `OrderRequest` passes safety checks and is submitted to
the configured live brokerage.

### Fields

| Field | Type | Required | Validation |
|---|---|---:|---|
| `submitted` | bool | yes | true only after broker submission returns |
| `dry_run` | bool | yes | false for the D1 submission path |
| `order_id` | string | yes | broker order ID |
| `client_order_id` | string | yes | original idempotency key |
| `symbol` | string | yes | uppercase |
| `status` | string | yes | normalized `OrderStatus` value |
| `order` | dict | yes | serialized normalized `Order` |
| `reconciliation` | dict/null | no | before-submit reconciliation payload |

### Validation Rules

- The result is produced only after `validate_live_order_submission_config`,
  `validate_live_account`, `validate_order_request_safety`, and reconciliation
  checks pass.
- Automated strategy-generated submissions reuse this result only after
  `validate_live_automated_submission_config` also passes and the automated
  kill switch is open.

### Producers

- `LiveEngine.submit_live_order`.

### Consumers

- live health/status output,
- operator runbooks,
- future audit persistence.
