"""Exchange calendar and market-session service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qts.core.exceptions import CalendarError, ConfigurationError
from qts.domain import normalize_timestamp


DEFAULT_EXCHANGE = "XNYS"
DEFAULT_SESSION_TIMEZONE = "America/New_York"
DEFAULT_REGULAR_OPEN = time(9, 30)
DEFAULT_REGULAR_CLOSE = time(16, 0)
DEFAULT_PREMARKET_OPEN = time(4, 0)
DEFAULT_AFTER_HOURS_CLOSE = time(20, 0)
DEFAULT_CALENDAR_PROVIDER = "builtin_us_equity"
EARLY_CLOSE_TIME = time(13, 0)
SUPPORTED_EXCHANGES = {"XNYS", "NASDAQ"}
EXCHANGE_ALIASES = {
    "NYSE": "XNYS",
    "XNYS": "XNYS",
    "XNAS": "NASDAQ",
    "NASDAQ": "NASDAQ",
}
SUPPORTED_PROVIDERS = {
    "builtin": DEFAULT_CALENDAR_PROVIDER,
    "builtin_us_equity": DEFAULT_CALENDAR_PROVIDER,
    "us_equity": DEFAULT_CALENDAR_PROVIDER,
}


@dataclass(frozen=True)
class ExtendedHoursConfig:
    """Extended-hours session settings."""

    enabled: bool = False
    premarket_open: time = DEFAULT_PREMARKET_OPEN
    after_hours_close: time = DEFAULT_AFTER_HOURS_CLOSE


@dataclass(frozen=True)
class MarketSessionConfig:
    """Validated runtime market-session configuration."""

    exchange: str = DEFAULT_EXCHANGE
    timezone: str = DEFAULT_SESSION_TIMEZONE
    regular_session_only: bool = True
    extended_hours: ExtendedHoursConfig = field(default_factory=ExtendedHoursConfig)
    fail_closed: bool = True
    calendar_provider: str = DEFAULT_CALENDAR_PROVIDER
    regular_open: time = DEFAULT_REGULAR_OPEN
    regular_close: time = DEFAULT_REGULAR_CLOSE

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "MarketSessionConfig":
        data = dict(raw or {})
        extended = _extended_hours_config(data.get("extended_hours"))
        config = cls(
            exchange=_normalize_exchange(data.get("exchange", DEFAULT_EXCHANGE)),
            timezone=_timezone_name(data.get("timezone", DEFAULT_SESSION_TIMEZONE)),
            regular_session_only=_optional_bool(data.get("regular_session_only"), True),
            extended_hours=extended,
            fail_closed=_optional_bool(data.get("fail_closed"), True),
            calendar_provider=_normalize_provider(
                data.get("calendar_provider", DEFAULT_CALENDAR_PROVIDER)
            ),
            regular_open=_parse_hhmm(data.get("regular_open", DEFAULT_REGULAR_OPEN), "regular_open"),
            regular_close=_parse_hhmm(
                data.get("regular_close", DEFAULT_REGULAR_CLOSE),
                "regular_close",
            ),
        )
        _validate_session_config(config)
        return config

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


DEFAULT_MARKET_SESSION_CONFIG = MarketSessionConfig()


@dataclass(frozen=True)
class MarketSession:
    """One resolved exchange session with UTC-normalized boundaries."""

    exchange: str
    session_date: date
    timezone: str
    regular_open: datetime
    regular_close: datetime
    premarket_open: datetime | None = None
    after_hours_close: datetime | None = None
    early_close: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tradable_open(self) -> datetime:
        return self.premarket_open or self.regular_open

    @property
    def tradable_close(self) -> datetime:
        return self.after_hours_close or self.regular_close

    def contains_regular(self, timestamp: datetime | str) -> bool:
        normalized = normalize_timestamp(timestamp, assume_utc_for_naive=True)
        return self.regular_open <= normalized < self.regular_close

    def contains_tradable(self, timestamp: datetime | str) -> bool:
        normalized = normalize_timestamp(timestamp, assume_utc_for_naive=True)
        return self.tradable_open <= normalized < self.tradable_close


class MarketCalendar(Protocol):
    """Provider interface for resolving exchange sessions."""

    def session_for_date(
        self,
        session_date: date,
        config: MarketSessionConfig,
    ) -> MarketSession | None:
        """Return a market session for a local date, or None when closed."""


class USEquityCalendar:
    """Deterministic built-in US equity calendar for XNYS/NASDAQ sessions."""

    def session_for_date(
        self,
        session_date: date,
        config: MarketSessionConfig,
    ) -> MarketSession | None:
        if config.exchange not in SUPPORTED_EXCHANGES:
            raise CalendarError(f"unsupported exchange for built-in calendar: {config.exchange}")
        if session_date.weekday() >= 5 or self.is_holiday(session_date):
            return None

        zone = config.zone
        early_close = self.is_early_close(session_date)
        close_time = min(config.regular_close, EARLY_CLOSE_TIME) if early_close else config.regular_close
        regular_open = _local_to_utc(session_date, config.regular_open, zone)
        regular_close = _local_to_utc(session_date, close_time, zone)

        premarket_open = None
        after_hours_close = None
        if config.extended_hours.enabled and not config.regular_session_only:
            premarket_open = _local_to_utc(
                session_date,
                config.extended_hours.premarket_open,
                zone,
            )
            after_hours_close = _local_to_utc(
                session_date,
                config.extended_hours.after_hours_close,
                zone,
            )

        return MarketSession(
            exchange=config.exchange,
            session_date=session_date,
            timezone=config.timezone,
            regular_open=regular_open,
            regular_close=regular_close,
            premarket_open=premarket_open,
            after_hours_close=after_hours_close,
            early_close=early_close,
            metadata={"provider": config.calendar_provider},
        )

    def is_holiday(self, session_date: date) -> bool:
        return session_date in _us_equity_holidays(session_date.year) or session_date in _us_equity_holidays(
            session_date.year + 1
        )

    def is_early_close(self, session_date: date) -> bool:
        if session_date.weekday() >= 5 or self.is_holiday(session_date):
            return False
        early_closes = {
            _thanksgiving(session_date.year) + timedelta(days=1),
            date(session_date.year, 12, 24),
        }
        july_third = date(session_date.year, 7, 3)
        if july_third.weekday() < 5 and july_third not in _us_equity_holidays(session_date.year):
            early_closes.add(july_third)
        return session_date in early_closes


class MarketSessionService:
    """Application-level session queries with UTC timestamp normalization."""

    def __init__(
        self,
        config: MarketSessionConfig | Mapping[str, Any] | None = None,
        *,
        provider: MarketCalendar | None = None,
    ) -> None:
        self.config = (
            config
            if isinstance(config, MarketSessionConfig)
            else MarketSessionConfig.from_mapping(config)
        )
        self.provider = provider or _provider_from_name(self.config.calendar_provider)

    def session_for_date(self, session_date: date) -> MarketSession | None:
        return self._session_for_date(session_date)

    def session_for_timestamp(self, timestamp: datetime | str) -> MarketSession | None:
        normalized = normalize_timestamp(timestamp, assume_utc_for_naive=True)
        local_date = normalized.astimezone(self.config.zone).date()
        return self._session_for_date(local_date)

    def is_session_day(self, session_date: date) -> bool:
        return self._session_for_date(session_date) is not None

    def is_regular_session(self, timestamp: datetime | str) -> bool:
        session = self.session_for_timestamp(timestamp)
        return False if session is None else session.contains_regular(timestamp)

    def is_tradable(self, timestamp: datetime | str) -> bool:
        session = self.session_for_timestamp(timestamp)
        return False if session is None else session.contains_tradable(timestamp)

    def is_early_close(self, timestamp_or_date: datetime | date | str) -> bool:
        if isinstance(timestamp_or_date, date) and not isinstance(timestamp_or_date, datetime):
            session_date = timestamp_or_date
        else:
            normalized = normalize_timestamp(timestamp_or_date, assume_utc_for_naive=True)
            session_date = normalized.astimezone(self.config.zone).date()
        session = self._session_for_date(session_date)
        return False if session is None else session.early_close

    def current_or_next_session(self, timestamp: datetime | str) -> MarketSession:
        normalized = normalize_timestamp(timestamp, assume_utc_for_naive=True)
        local_date = normalized.astimezone(self.config.zone).date()
        current = self._session_for_date(local_date)
        if current is not None and normalized < current.tradable_close:
            return current
        return self.next_session_after(normalized)

    def next_session_after(self, timestamp: datetime | str) -> MarketSession:
        normalized = normalize_timestamp(timestamp, assume_utc_for_naive=True)
        start_date = normalized.astimezone(self.config.zone).date()
        for offset in range(1, 15):
            session = self._session_for_date(start_date + timedelta(days=offset))
            if session is not None:
                return session
        raise CalendarError("could not resolve next market session within 14 days")

    def _session_for_date(self, session_date: date) -> MarketSession | None:
        try:
            return self.provider.session_for_date(session_date, self.config)
        except Exception as exc:
            if self.config.fail_closed:
                return None
            if isinstance(exc, CalendarError):
                raise
            raise CalendarError(f"could not resolve market session: {exc}") from exc


def market_session_config_from_mapping(raw: Mapping[str, Any] | None) -> MarketSessionConfig:
    return MarketSessionConfig.from_mapping(raw)


def build_market_session_service(
    config_or_mapping: Any,
    *,
    provider: MarketCalendar | None = None,
) -> MarketSessionService:
    raw = getattr(config_or_mapping, "market_session", config_or_mapping)
    return MarketSessionService(raw, provider=provider)


def default_market_session_service() -> MarketSessionService:
    return MarketSessionService(DEFAULT_MARKET_SESSION_CONFIG)


def _provider_from_name(name: str) -> MarketCalendar:
    normalized = _normalize_provider(name)
    if normalized == DEFAULT_CALENDAR_PROVIDER:
        return USEquityCalendar()
    raise CalendarError(f"unsupported market calendar provider: {name}")


def _normalize_exchange(value: Any) -> str:
    text = str(value or "").strip().upper()
    exchange = EXCHANGE_ALIASES.get(text)
    if exchange is None:
        allowed = ", ".join(sorted(SUPPORTED_EXCHANGES | set(EXCHANGE_ALIASES)))
        raise ConfigurationError(f"unsupported market_session.exchange {value!r}; expected one of {allowed}")
    return exchange


def _normalize_provider(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    provider = SUPPORTED_PROVIDERS.get(text)
    if provider is None:
        allowed = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ConfigurationError(
            f"unsupported market_session.calendar_provider {value!r}; expected one of {allowed}"
        )
    return provider


def _timezone_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ConfigurationError("market_session.timezone must be non-empty")
    try:
        ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"unknown market_session.timezone: {text}") from exc
    return text


def _extended_hours_config(raw: Any) -> ExtendedHoursConfig:
    if raw is None:
        return ExtendedHoursConfig()
    if isinstance(raw, bool):
        return ExtendedHoursConfig(enabled=raw)
    if not isinstance(raw, Mapping):
        raise ConfigurationError("market_session.extended_hours must be a mapping or boolean")
    return ExtendedHoursConfig(
        enabled=_optional_bool(raw.get("enabled"), False),
        premarket_open=_parse_hhmm(
            raw.get("premarket_open", DEFAULT_PREMARKET_OPEN),
            "extended_hours.premarket_open",
        ),
        after_hours_close=_parse_hhmm(
            raw.get("after_hours_close", DEFAULT_AFTER_HOURS_CLOSE),
            "extended_hours.after_hours_close",
        ),
    )


def _validate_session_config(config: MarketSessionConfig) -> None:
    if config.regular_open >= config.regular_close:
        raise ConfigurationError("market_session.regular_open must be before regular_close")
    if config.extended_hours.enabled:
        if config.extended_hours.premarket_open >= config.regular_open:
            raise ConfigurationError("premarket_open must be before regular_open")
        if config.extended_hours.after_hours_close <= config.regular_close:
            raise ConfigurationError("after_hours_close must be after regular_close")


def _optional_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _parse_hhmm(value: Any, field_name: str) -> time:
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"market_session.{field_name} must be HH:MM") from exc


def _local_to_utc(session_date: date, local_time: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(session_date, local_time, tzinfo=zone).astimezone(ZoneInfo("UTC"))


def _us_equity_holidays(year: int) -> set[date]:
    thanksgiving = _thanksgiving(year)
    holidays = {
        _observed_fixed(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_fixed(year, 6, 19),
        _observed_fixed(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        thanksgiving,
        _observed_fixed(year, 12, 25),
    }
    return holidays


def _observed_fixed(year: int, month: int, day: int) -> date:
    actual = date(year, month, day)
    if actual.weekday() == 5:
        return actual - timedelta(days=1)
    if actual.weekday() == 6:
        return actual + timedelta(days=1)
    return actual


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    days_until = (weekday - first.weekday()) % 7
    return first + timedelta(days=days_until + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year, 12, 31)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _thanksgiving(year: int) -> date:
    return _nth_weekday(year, 11, 3, 4)


def _easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    correction = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * correction) // 451
    month = (h + correction - 7 * m + 114) // 31
    day = ((h + correction - 7 * m + 114) % 31) + 1
    return date(year, month, day)


__all__ = [
    "DEFAULT_MARKET_SESSION_CONFIG",
    "ExtendedHoursConfig",
    "MarketCalendar",
    "MarketSession",
    "MarketSessionConfig",
    "MarketSessionService",
    "USEquityCalendar",
    "build_market_session_service",
    "default_market_session_service",
    "market_session_config_from_mapping",
]
