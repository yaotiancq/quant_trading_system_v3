"""Validated domain models shared across runtime modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Any, TypeVar

from .enums import (
    BarTimeframe,
    BrokerEventType,
    DataAdjustment,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
    RuntimeMode,
    SignalDirection,
    TimeInForce,
)


EnumT = TypeVar("EnumT", bound=Enum)
UTC = timezone.utc


def normalize_timestamp(
    value: datetime | date | str,
    *,
    end_of_day: bool = False,
    assume_utc_for_naive: bool = False,
) -> datetime:
    """Normalize a timestamp-like value to timezone-aware UTC."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.max if end_of_day else time.min, tzinfo=UTC)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("timestamp cannot be empty")
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        parsed = datetime.fromisoformat(raw)
        if isinstance(parsed, datetime):
            dt = parsed
        else:
            raise ValueError(f"unsupported timestamp value: {value!r}")
    else:
        raise TypeError(f"unsupported timestamp type: {type(value).__name__}")

    if (dt.tzinfo is None or dt.utcoffset() is None) and assume_utc_for_naive:
        dt = dt.replace(tzinfo=UTC)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(UTC)


def normalize_symbol(value: str) -> str:
    symbol = str(value).strip().upper()
    if not symbol:
        raise ValueError("symbol must be non-empty")
    return symbol


def normalize_symbols(values: list[str] | tuple[str, ...]) -> list[str]:
    if not values:
        raise ValueError("symbols must be non-empty")
    return [normalize_symbol(value) for value in values]


def normalize_currency(value: str) -> str:
    currency = str(value).strip().upper()
    if not currency:
        raise ValueError("currency must be non-empty")
    return currency


def coerce_enum(enum_type: type[EnumT], value: EnumT | str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value).strip().upper())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{value!r} is not a valid {enum_type.__name__}; expected one of {allowed}") from exc


def _require_text(value: str | None, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _non_negative(value: float | int | None, field_name: str) -> float | int | None:
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _positive(value: float | int | None, field_name: str) -> float | int | None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _range(value: float | None, field_name: str, minimum: float, maximum: float) -> float | None:
    if value is not None and not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return value


def _dict(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _list(value: list[Any] | tuple[Any, ...] | None) -> list[Any]:
    return list(value or [])


def _validate_order_prices(
    order_type: OrderType,
    limit_price: float | None,
    stop_price: float | None,
) -> None:
    if order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and limit_price is None:
        raise ValueError("limit_price is required for LIMIT and STOP_LIMIT orders")
    if order_type in {OrderType.STOP, OrderType.STOP_LIMIT} and stop_price is None:
        raise ValueError("stop_price is required for STOP and STOP_LIMIT orders")
    _positive(limit_price, "limit_price")
    _positive(stop_price, "stop_price")


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        text = value.astimezone(UTC).isoformat()
        return text.replace("+00:00", "Z")
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class DomainModel:
    """Mixin that gives domain dataclasses stable serialization helpers."""

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Bar(DomainModel):
    symbol: str
    timestamp: datetime
    timeframe: BarTimeframe | str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    trade_count: int | None = None
    source: str | None = None
    bar_interval: str | None = None
    adjustment: DataAdjustment | str = DataAdjustment.RAW

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.timeframe = coerce_enum(BarTimeframe, self.timeframe)
        for name in ("open", "high", "low", "close", "volume"):
            _non_negative(getattr(self, name), name)
        _non_negative(self.vwap, "vwap")
        _non_negative(self.trade_count, "trade_count")
        self.source = _optional_text(self.source)
        self.bar_interval = _optional_text(self.bar_interval)
        self.adjustment = coerce_enum(DataAdjustment, self.adjustment)
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high")


@dataclass
class Quote(DomainModel):
    symbol: str
    timestamp: datetime
    bid_price: float
    ask_price: float
    bid_size: float | None = None
    ask_size: float | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        _non_negative(self.bid_price, "bid_price")
        _non_negative(self.ask_price, "ask_price")
        _non_negative(self.bid_size, "bid_size")
        _non_negative(self.ask_size, "ask_size")
        self.source = _optional_text(self.source)
        if self.ask_price < self.bid_price:
            raise ValueError("ask_price must be greater than or equal to bid_price")


@dataclass
class Trade(DomainModel):
    symbol: str
    timestamp: datetime
    price: float
    size: float
    exchange: str | None = None
    conditions: list[str] = field(default_factory=list)
    source: str | None = None

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        _positive(self.price, "price")
        _positive(self.size, "size")
        self.exchange = _optional_text(self.exchange)
        self.conditions = [str(condition) for condition in self.conditions]
        self.source = _optional_text(self.source)


@dataclass
class Signal(DomainModel):
    signal_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    direction: SignalDirection | str
    strength: float | None = None
    confidence: float | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.signal_id = _require_text(self.signal_id, "signal_id")
        self.strategy_id = _require_text(self.strategy_id, "strategy_id")
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.direction = coerce_enum(SignalDirection, self.direction)
        _range(self.strength, "strength", -1.0, 1.0)
        _range(self.confidence, "confidence", 0.0, 1.0)
        self.reason = _optional_text(self.reason)
        self.metadata = _dict(self.metadata)


@dataclass
class TargetPosition(DomainModel):
    target_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    target_quantity: float | None = None
    target_weight: float | None = None
    target_notional: float | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.target_id = _require_text(self.target_id, "target_id")
        self.strategy_id = _require_text(self.strategy_id, "strategy_id")
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        if all(value is None for value in (self.target_quantity, self.target_weight, self.target_notional)):
            raise ValueError("one target quantity, weight, or notional value is required")
        _range(self.target_weight, "target_weight", -1.0, 1.0)
        _non_negative(self.target_notional, "target_notional")
        self.reason = _optional_text(self.reason)
        self.metadata = _dict(self.metadata)


@dataclass
class TradeIntent(DomainModel):
    intent_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    side: OrderSide | str
    quantity: float | None = None
    notional: float | None = None
    order_type: OrderType | str = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    time_in_force: TimeInForce | str = TimeInForce.DAY
    source_signal_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.intent_id = _require_text(self.intent_id, "intent_id")
        self.strategy_id = _require_text(self.strategy_id, "strategy_id")
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.side = coerce_enum(OrderSide, self.side)
        self.order_type = coerce_enum(OrderType, self.order_type)
        self.time_in_force = coerce_enum(TimeInForce, self.time_in_force)
        _positive(self.quantity, "quantity")
        _positive(self.notional, "notional")
        if self.quantity is not None and self.notional is not None:
            raise ValueError("provide either quantity or notional, not both")
        _validate_order_prices(self.order_type, self.limit_price, self.stop_price)
        self.source_signal_id = _optional_text(self.source_signal_id)
        self.reason = _optional_text(self.reason)
        self.metadata = _dict(self.metadata)


@dataclass
class RiskDecision(DomainModel):
    decision_id: str
    timestamp: datetime
    status: RiskDecisionStatus | str
    original_intent: TradeIntent
    approved_intent: TradeIntent | None = None
    reasons: list[str] = field(default_factory=list)
    rule_results: list[dict[str, Any]] = field(default_factory=list)
    sizing_details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.decision_id = _require_text(self.decision_id, "decision_id")
        self.timestamp = normalize_timestamp(self.timestamp)
        self.status = coerce_enum(RiskDecisionStatus, self.status)
        if not isinstance(self.original_intent, TradeIntent):
            raise TypeError("original_intent must be a TradeIntent")
        if self.approved_intent is not None and not isinstance(self.approved_intent, TradeIntent):
            raise TypeError("approved_intent must be a TradeIntent")
        self.reasons = [str(reason) for reason in self.reasons]
        if self.status in {RiskDecisionStatus.REJECTED, RiskDecisionStatus.MODIFIED} and not self.reasons:
            raise ValueError("reasons are required for rejected or modified risk decisions")
        if self.status in {RiskDecisionStatus.APPROVED, RiskDecisionStatus.MODIFIED} and self.approved_intent is None:
            raise ValueError("approved_intent is required for approved or modified risk decisions")
        self.rule_results = [dict(result) for result in self.rule_results]
        self.sizing_details = _dict(self.sizing_details)


@dataclass
class OrderRequest(DomainModel):
    client_order_id: str
    symbol: str
    timestamp: datetime
    side: OrderSide | str
    order_type: OrderType | str
    time_in_force: TimeInForce | str
    strategy_id: str | None = None
    quantity: float | None = None
    notional: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.client_order_id = _require_text(self.client_order_id, "client_order_id")
        self.strategy_id = _optional_text(self.strategy_id)
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.side = coerce_enum(OrderSide, self.side)
        self.order_type = coerce_enum(OrderType, self.order_type)
        self.time_in_force = coerce_enum(TimeInForce, self.time_in_force)
        _positive(self.quantity, "quantity")
        _positive(self.notional, "notional")
        if (self.quantity is None) == (self.notional is None):
            raise ValueError("exactly one of quantity or notional is required")
        _validate_order_prices(self.order_type, self.limit_price, self.stop_price)
        self.metadata = _dict(self.metadata)


@dataclass
class Order(DomainModel):
    order_id: str
    client_order_id: str
    symbol: str
    created_at: datetime
    side: OrderSide | str
    filled_quantity: float
    order_type: OrderType | str
    status: OrderStatus | str
    quantity: float | None = None
    updated_at: datetime | None = None
    remaining_quantity: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    average_fill_price: float | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.order_id = _require_text(self.order_id, "order_id")
        self.client_order_id = _require_text(self.client_order_id, "client_order_id")
        self.symbol = normalize_symbol(self.symbol)
        self.created_at = normalize_timestamp(self.created_at)
        self.updated_at = normalize_timestamp(self.updated_at) if self.updated_at is not None else None
        self.side = coerce_enum(OrderSide, self.side)
        self.order_type = coerce_enum(OrderType, self.order_type)
        self.status = coerce_enum(OrderStatus, self.status)
        _positive(self.quantity, "quantity")
        _non_negative(self.filled_quantity, "filled_quantity")
        _non_negative(self.remaining_quantity, "remaining_quantity")
        _positive(self.limit_price, "limit_price")
        _positive(self.stop_price, "stop_price")
        _non_negative(self.average_fill_price, "average_fill_price")
        if self.status == OrderStatus.REJECTED and not _optional_text(self.rejection_reason):
            raise ValueError("rejection_reason is required for rejected orders")
        self.rejection_reason = _optional_text(self.rejection_reason)
        self.metadata = _dict(self.metadata)


@dataclass
class Fill(DomainModel):
    fill_id: str
    order_id: str
    symbol: str
    timestamp: datetime
    side: OrderSide | str
    quantity: float
    price: float
    commission: float
    source: str
    client_order_id: str | None = None
    slippage: float | None = None
    liquidity_flag: str | None = None

    def __post_init__(self) -> None:
        self.fill_id = _require_text(self.fill_id, "fill_id")
        self.order_id = _require_text(self.order_id, "order_id")
        self.client_order_id = _optional_text(self.client_order_id)
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.side = coerce_enum(OrderSide, self.side)
        _positive(self.quantity, "quantity")
        _positive(self.price, "price")
        _non_negative(self.commission, "commission")
        _non_negative(self.slippage, "slippage")
        self.liquidity_flag = _optional_text(self.liquidity_flag)
        self.source = _require_text(self.source, "source")


@dataclass
class Position(DomainModel):
    symbol: str
    quantity: float
    average_cost: float
    updated_at: datetime
    market_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        self.updated_at = normalize_timestamp(self.updated_at)
        _non_negative(self.average_cost, "average_cost")
        _non_negative(self.market_price, "market_price")
        if self.market_value is None and self.market_price is not None:
            self.market_value = abs(self.quantity * self.market_price)
        if self.unrealized_pnl is None and self.market_price is not None:
            self.unrealized_pnl = (self.market_price - self.average_cost) * self.quantity
        _non_negative(self.market_value, "market_value")


@dataclass
class BrokerEvent(DomainModel):
    event_id: str
    event_type: BrokerEventType | str
    timestamp: datetime
    source: str
    order: Order | None = None
    fill: Fill | None = None
    account: Account | None = None
    position: Position | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_id = _require_text(self.event_id, "event_id")
        self.event_type = coerce_enum(BrokerEventType, self.event_type)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.source = _require_text(self.source, "source")
        self.metadata = _dict(self.metadata)

        payloads = [self.order, self.fill, self.account, self.position]
        if sum(item is not None for item in payloads) != 1:
            raise ValueError("broker event requires exactly one payload")
        if self.order is not None and not isinstance(self.order, Order):
            raise TypeError("order payload must be an Order")
        if self.fill is not None and not isinstance(self.fill, Fill):
            raise TypeError("fill payload must be a Fill")
        if self.account is not None and not isinstance(self.account, Account):
            raise TypeError("account payload must be an Account")
        if self.position is not None and not isinstance(self.position, Position):
            raise TypeError("position payload must be a Position")
        expected_payload = {
            BrokerEventType.ORDER_UPDATE: self.order,
            BrokerEventType.FILL: self.fill,
            BrokerEventType.ACCOUNT_UPDATE: self.account,
            BrokerEventType.POSITION_UPDATE: self.position,
        }[self.event_type]
        if expected_payload is None:
            raise ValueError(f"{self.event_type.value} broker event has wrong payload")


@dataclass
class Account(DomainModel):
    timestamp: datetime
    cash: float
    equity: float
    buying_power: float
    account_id: str | None = None
    currency: str = "USD"
    gross_exposure: float | None = None
    net_exposure: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.account_id = _optional_text(self.account_id)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.currency = normalize_currency(self.currency)
        _non_negative(self.buying_power, "buying_power")
        _non_negative(self.gross_exposure, "gross_exposure")
        self.metadata = _dict(self.metadata)


@dataclass
class PortfolioSnapshot(DomainModel):
    timestamp: datetime
    cash: float
    equity: float
    positions_value: float
    realized_pnl: float
    unrealized_pnl: float
    gross_exposure: float
    net_exposure: float
    positions: list[Position] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.timestamp = normalize_timestamp(self.timestamp)
        _non_negative(self.positions_value, "positions_value")
        _non_negative(self.gross_exposure, "gross_exposure")
        if not all(isinstance(position, Position) for position in self.positions):
            raise TypeError("positions must be Position instances")
        self.metadata = _dict(self.metadata)


@dataclass
class TradeLedgerEntry(DomainModel):
    entry_id: str
    fill_id: str
    order_id: str
    symbol: str
    timestamp: datetime
    side: OrderSide | str
    quantity: float
    price: float
    commission: float
    position_quantity_after: float
    average_cost_after: float
    strategy_id: str | None = None
    realized_pnl_delta: float | None = None

    def __post_init__(self) -> None:
        self.entry_id = _require_text(self.entry_id, "entry_id")
        self.fill_id = _require_text(self.fill_id, "fill_id")
        self.order_id = _require_text(self.order_id, "order_id")
        self.strategy_id = _optional_text(self.strategy_id)
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.side = coerce_enum(OrderSide, self.side)
        _positive(self.quantity, "quantity")
        _positive(self.price, "price")
        _non_negative(self.commission, "commission")
        _non_negative(self.average_cost_after, "average_cost_after")


@dataclass
class CashLedgerEntry(DomainModel):
    entry_id: str
    timestamp: datetime
    event_type: str
    amount: float
    currency: str
    cash_after: float
    related_fill_id: str | None = None
    related_order_id: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        self.entry_id = _require_text(self.entry_id, "entry_id")
        self.timestamp = normalize_timestamp(self.timestamp)
        self.event_type = _require_text(self.event_type, "event_type")
        self.currency = normalize_currency(self.currency)
        self.related_fill_id = _optional_text(self.related_fill_id)
        self.related_order_id = _optional_text(self.related_order_id)
        self.description = _optional_text(self.description)


@dataclass
class FeatureFrame(DomainModel):
    symbols: list[str]
    timestamps: list[datetime]
    features: Any
    schema_version: str
    generated_at: datetime
    source: str | None = None

    def __post_init__(self) -> None:
        self.symbols = normalize_symbols(self.symbols)
        self.timestamps = [normalize_timestamp(ts) for ts in self.timestamps]
        if any(left > right for left, right in zip(self.timestamps, self.timestamps[1:])):
            raise ValueError("timestamps must be ordered")
        self.schema_version = _require_text(self.schema_version, "schema_version")
        self.generated_at = normalize_timestamp(self.generated_at)
        self.source = _optional_text(self.source)


@dataclass
class FeatureRecord(DomainModel):
    symbol: str
    timestamp: datetime
    values: dict[str, float]
    schema_version: str

    def __post_init__(self) -> None:
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.values = dict(self.values)
        if not self.values:
            raise ValueError("values must be non-empty")
        self.schema_version = _require_text(self.schema_version, "schema_version")


@dataclass
class ModelPrediction(DomainModel):
    prediction_id: str
    model_id: str
    symbol: str
    timestamp: datetime
    prediction_value: float
    feature_schema_version: str
    prediction_label: str | int | None = None
    probability: float | None = None
    horizon: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.prediction_id = _require_text(self.prediction_id, "prediction_id")
        self.model_id = _require_text(self.model_id, "model_id")
        self.symbol = normalize_symbol(self.symbol)
        self.timestamp = normalize_timestamp(self.timestamp)
        self.feature_schema_version = _require_text(
            self.feature_schema_version, "feature_schema_version"
        )
        _range(self.probability, "probability", 0.0, 1.0)
        self.horizon = _optional_text(self.horizon)
        self.metadata = _dict(self.metadata)


@dataclass
class StrategyConfig(DomainModel):
    strategy_id: str
    strategy_type: str
    symbols: list[str]
    parameters: dict[str, Any] = field(default_factory=dict)
    feature_config: dict[str, Any] | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        self.strategy_id = _require_text(self.strategy_id, "strategy_id")
        self.strategy_type = _require_text(self.strategy_type, "strategy_type")
        self.symbols = normalize_symbols(self.symbols)
        self.parameters = _dict(self.parameters)
        self.feature_config = _dict(self.feature_config)
        self.enabled = bool(self.enabled)


@dataclass
class RiskConfig(DomainModel):
    sizing_method: str
    sizing_parameters: dict[str, Any] = field(default_factory=dict)
    max_position_notional: float | None = None
    max_gross_exposure: float | None = None
    max_symbol_weight: float | None = None
    daily_loss_limit: float | None = None
    allowed_symbols: list[str] | None = None
    blocked_symbols: list[str] | None = None
    cooldown_seconds: int | None = None
    session_rules: dict[str, Any] | None = None
    disabled_until_configured: bool = False

    def __post_init__(self) -> None:
        self.sizing_method = _require_text(self.sizing_method, "sizing_method")
        self.sizing_parameters = _dict(self.sizing_parameters)
        _positive(self.max_position_notional, "max_position_notional")
        _positive(self.max_gross_exposure, "max_gross_exposure")
        _range(self.max_symbol_weight, "max_symbol_weight", 0.0, 1.0)
        _positive(self.daily_loss_limit, "daily_loss_limit")
        self.allowed_symbols = normalize_symbols(self.allowed_symbols) if self.allowed_symbols else None
        self.blocked_symbols = normalize_symbols(self.blocked_symbols) if self.blocked_symbols else None
        _non_negative(self.cooldown_seconds, "cooldown_seconds")
        self.session_rules = _dict(self.session_rules)
        self.disabled_until_configured = bool(self.disabled_until_configured)


@dataclass
class BrokerConfig(DomainModel):
    broker_type: str
    account_id: str | None = None
    paper: bool | None = None
    base_url: str | None = None
    credential_env_keys: dict[str, str] | None = None
    commission_model: dict[str, Any] | None = None
    slippage_model: dict[str, Any] | None = None
    fill_policy: str | None = None
    safety: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.broker_type = _require_text(self.broker_type, "broker_type")
        self.account_id = _optional_text(self.account_id)
        self.base_url = _optional_text(self.base_url)
        self.credential_env_keys = _dict(self.credential_env_keys)
        self.commission_model = _dict(self.commission_model)
        self.slippage_model = _dict(self.slippage_model)
        self.fill_policy = _optional_text(self.fill_policy)
        self.safety = _dict(self.safety)


@dataclass
class RuntimeConfig(DomainModel):
    run_id: str
    runtime_mode: RuntimeMode | str
    symbols: list[str]
    timeframe: BarTimeframe | str
    market_data: dict[str, Any]
    broker: BrokerConfig
    strategies: list[StrategyConfig]
    risk: RiskConfig
    portfolio: dict[str, Any]
    execution: dict[str, Any]
    start: datetime | date | str | None = None
    end: datetime | date | str | None = None
    bar_interval: str | None = None
    market_session: dict[str, Any] = field(default_factory=dict)
    reporting: dict[str, Any] = field(default_factory=dict)
    monitoring: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.run_id = _require_text(self.run_id, "run_id")
        self.runtime_mode = coerce_enum(RuntimeMode, self.runtime_mode)
        self.symbols = normalize_symbols(self.symbols)
        self.timeframe = coerce_enum(BarTimeframe, self.timeframe)
        self.bar_interval = _optional_text(self.bar_interval)
        self.market_data = _dict(self.market_data)
        if not self.market_data:
            raise ValueError("market_data must be non-empty")
        if not isinstance(self.broker, BrokerConfig):
            self.broker = BrokerConfig(**self.broker)
        self.strategies = [
            strategy if isinstance(strategy, StrategyConfig) else StrategyConfig(**strategy)
            for strategy in self.strategies
        ]
        if not any(strategy.enabled for strategy in self.strategies):
            raise ValueError("at least one strategy must be enabled")
        if not isinstance(self.risk, RiskConfig):
            self.risk = RiskConfig(**self.risk)
        self.portfolio = _dict(self.portfolio)
        self.execution = _dict(self.execution)
        if not self.portfolio:
            raise ValueError("portfolio must be non-empty")
        if not self.execution:
            raise ValueError("execution must be non-empty")
        self.market_session = _dict(self.market_session)
        self.start = (
            normalize_timestamp(self.start, assume_utc_for_naive=True)
            if self.start is not None
            else None
        )
        self.end = (
            normalize_timestamp(self.end, end_of_day=True, assume_utc_for_naive=True)
            if self.end is not None
            else None
        )
        if self.runtime_mode == RuntimeMode.BACKTEST and (self.start is None or self.end is None):
            raise ValueError("backtest config requires start and end")
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        self.reporting = _dict(self.reporting)
        self.monitoring = _dict(self.monitoring)
        self.metadata = _dict(self.metadata)


@dataclass
class BacktestResult(DomainModel):
    run_id: str
    config: RuntimeConfig
    start_time: datetime
    end_time: datetime
    symbols: list[str]
    portfolio_snapshots: list[PortfolioSnapshot]
    orders: list[Order]
    fills: list[Fill]
    trade_ledger: list[TradeLedgerEntry]
    cash_ledger: list[CashLedgerEntry]
    metrics: dict[str, Any]
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.run_id = _require_text(self.run_id, "run_id")
        if not isinstance(self.config, RuntimeConfig):
            raise TypeError("config must be a RuntimeConfig")
        self.start_time = normalize_timestamp(self.start_time)
        self.end_time = normalize_timestamp(self.end_time)
        if self.end_time < self.start_time:
            raise ValueError("end_time must be greater than or equal to start_time")
        self.symbols = normalize_symbols(self.symbols)
        if not all(isinstance(snapshot, PortfolioSnapshot) for snapshot in self.portfolio_snapshots):
            raise TypeError("portfolio_snapshots must contain PortfolioSnapshot instances")
        if any(
            left.timestamp > right.timestamp
            for left, right in zip(self.portfolio_snapshots, self.portfolio_snapshots[1:])
        ):
            raise ValueError("portfolio_snapshots must be ordered by timestamp")
        if not all(isinstance(order, Order) for order in self.orders):
            raise TypeError("orders must contain Order instances")
        if not all(isinstance(fill, Fill) for fill in self.fills):
            raise TypeError("fills must contain Fill instances")
        self.metrics = _dict(self.metrics)
        self.artifacts = _dict(self.artifacts)
        self.warnings = [str(warning) for warning in self.warnings]


__all__ = [
    "Account",
    "BacktestResult",
    "Bar",
    "BrokerConfig",
    "CashLedgerEntry",
    "DomainModel",
    "FeatureFrame",
    "FeatureRecord",
    "Fill",
    "ModelPrediction",
    "Order",
    "OrderRequest",
    "PortfolioSnapshot",
    "Position",
    "Quote",
    "RiskConfig",
    "RiskDecision",
    "RuntimeConfig",
    "Signal",
    "StrategyConfig",
    "TargetPosition",
    "Trade",
    "TradeIntent",
    "TradeLedgerEntry",
    "coerce_enum",
    "normalize_currency",
    "normalize_symbol",
    "normalize_symbols",
    "normalize_timestamp",
]
