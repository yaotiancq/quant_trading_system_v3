"""Reusable batch indicator functions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from qts.core import FeatureError
from qts.domain import Bar


FeatureSeries = list[float | None]


class Indicator(Protocol):
    """Indicator contract matching the project interface document."""

    @property
    def name(self) -> str:
        """Stable indicator name."""

    @property
    def required_inputs(self) -> list[str]:
        """Required bar fields."""

    @property
    def lookback(self) -> int:
        """Minimum history required for a finite value."""

    def compute_batch(self, bars: Sequence[Bar]) -> dict[str, FeatureSeries]:
        """Compute one or more named feature series."""

    def update(self, bar: Bar) -> dict[str, float | None]:
        """Update online state and return latest values."""

    def reset(self) -> None:
        """Clear online state."""


@dataclass
class BatchIndicator:
    """Thin stateful wrapper around the built-in batch indicator functions."""

    name: str
    parameters: dict[str, int | float] = field(default_factory=dict)
    _bars: list[Bar] = field(default_factory=list, init=False, repr=False)

    @property
    def required_inputs(self) -> list[str]:
        return required_inputs_for(self.name)

    @property
    def lookback(self) -> int:
        return lookback_for(self.name, self.parameters)

    def compute_batch(self, bars: Sequence[Bar]) -> dict[str, FeatureSeries]:
        return compute_indicator(self.name, bars, self.parameters)

    def update(self, bar: Bar) -> dict[str, float | None]:
        self._bars.append(bar)
        values = self.compute_batch(self._bars)
        return {name: series[-1] for name, series in values.items()}

    def reset(self) -> None:
        self._bars.clear()


def compute_indicator(
    name: str,
    bars: Sequence[Bar],
    parameters: dict[str, int | float] | None = None,
) -> dict[str, FeatureSeries]:
    indicator_name = name.lower()
    params = dict(parameters or {})
    if indicator_name == "sma":
        window = _window(params, default=20)
        return {f"sma_{window}": sma(closes(bars), window)}
    if indicator_name == "ema":
        window = _window(params, default=20)
        return {f"ema_{window}": ema(closes(bars), window)}
    if indicator_name == "rsi":
        window = _window(params, default=14)
        return {f"rsi_{window}": rsi(closes(bars), window)}
    if indicator_name == "macd":
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal_window = int(params.get("signal", 9))
        line, signal, hist = macd(closes(bars), fast=fast, slow=slow, signal=signal_window)
        suffix = f"{fast}_{slow}_{signal_window}"
        return {
            f"macd_{suffix}": line,
            f"macd_signal_{suffix}": signal,
            f"macd_hist_{suffix}": hist,
        }
    if indicator_name == "bollinger":
        window = _window(params, default=20)
        stdevs = float(params.get("stdevs", 2.0))
        middle, upper, lower = bollinger_bands(closes(bars), window=window, stdevs=stdevs)
        return {
            f"bollinger_mid_{window}": middle,
            f"bollinger_upper_{window}": upper,
            f"bollinger_lower_{window}": lower,
        }
    if indicator_name == "atr":
        window = _window(params, default=14)
        return {f"atr_{window}": atr(bars, window)}
    if indicator_name == "vwap":
        return {"vwap": vwap(bars)}
    if indicator_name in {"returns", "return"}:
        window = _window(params, default=1)
        return {f"ret_{window}": returns(closes(bars), window)}
    if indicator_name == "volatility":
        window = _window(params, default=20)
        ret_window = int(params.get("return_window", 1))
        return {f"vol_{window}": volatility(closes(bars), window=window, return_window=ret_window)}
    if indicator_name in {"volume_mean", "volume"}:
        window = _window(params, default=20)
        return {f"volume_mean_{window}": sma(volumes(bars), window)}
    if indicator_name == "volume_ratio":
        window = _window(params, default=20)
        return {f"volume_ratio_{window}": volume_ratio(bars, window)}
    raise FeatureError(f"unsupported indicator: {name}")


def output_names_for(name: str, parameters: dict[str, int | float] | None = None) -> list[str]:
    params = dict(parameters or {})
    indicator_name = name.lower()
    if indicator_name == "sma":
        return [f"sma_{_window(params, default=20)}"]
    if indicator_name == "ema":
        return [f"ema_{_window(params, default=20)}"]
    if indicator_name == "rsi":
        return [f"rsi_{_window(params, default=14)}"]
    if indicator_name == "macd":
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal_window = int(params.get("signal", 9))
        suffix = f"{fast}_{slow}_{signal_window}"
        return [f"macd_{suffix}", f"macd_signal_{suffix}", f"macd_hist_{suffix}"]
    if indicator_name == "bollinger":
        window = _window(params, default=20)
        return [f"bollinger_mid_{window}", f"bollinger_upper_{window}", f"bollinger_lower_{window}"]
    if indicator_name == "atr":
        return [f"atr_{_window(params, default=14)}"]
    if indicator_name == "vwap":
        return ["vwap"]
    if indicator_name in {"returns", "return"}:
        return [f"ret_{_window(params, default=1)}"]
    if indicator_name == "volatility":
        return [f"vol_{_window(params, default=20)}"]
    if indicator_name in {"volume_mean", "volume"}:
        return [f"volume_mean_{_window(params, default=20)}"]
    if indicator_name == "volume_ratio":
        return [f"volume_ratio_{_window(params, default=20)}"]
    raise FeatureError(f"unsupported indicator: {name}")


def required_inputs_for(name: str) -> list[str]:
    indicator_name = name.lower()
    if indicator_name in {"sma", "ema", "rsi", "macd", "bollinger", "returns", "return", "volatility"}:
        return ["close"]
    if indicator_name in {"atr", "vwap"}:
        return ["high", "low", "close", "volume"]
    if indicator_name in {"volume_mean", "volume", "volume_ratio"}:
        return ["volume"]
    raise FeatureError(f"unsupported indicator: {name}")


def lookback_for(name: str, parameters: dict[str, int | float] | None = None) -> int:
    indicator_name = name.lower()
    params = dict(parameters or {})
    if indicator_name == "macd":
        return int(params.get("slow", 26)) + int(params.get("signal", 9)) - 1
    if indicator_name in {"vwap"}:
        return 1
    return _window(params, default=14 if indicator_name in {"rsi", "atr"} else 20)


def closes(bars: Sequence[Bar]) -> list[float]:
    return [float(bar.close) for bar in bars]


def highs(bars: Sequence[Bar]) -> list[float]:
    return [float(bar.high) for bar in bars]


def lows(bars: Sequence[Bar]) -> list[float]:
    return [float(bar.low) for bar in bars]


def volumes(bars: Sequence[Bar]) -> list[float]:
    return [float(bar.volume) for bar in bars]


def sma(values: Sequence[float], window: int) -> FeatureSeries:
    _validate_window(window)
    output: FeatureSeries = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
        else:
            chunk = values[index + 1 - window : index + 1]
            output.append(sum(chunk) / window)
    return output


def ema(values: Sequence[float], window: int) -> FeatureSeries:
    _validate_window(window)
    if not values:
        return []
    alpha = 2.0 / (window + 1.0)
    output: FeatureSeries = []
    current: float | None = None
    for index, value in enumerate(values):
        if index + 1 < window:
            output.append(None)
            continue
        if current is None:
            current = sum(values[:window]) / window
        else:
            current = (value - current) * alpha + current
        output.append(current)
    return output


def rsi(values: Sequence[float], window: int) -> FeatureSeries:
    _validate_window(window)
    output: FeatureSeries = [None] * len(values)
    if len(values) <= window:
        return output

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, window + 1):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    output[window] = _rsi_from_averages(avg_gain, avg_loss)

    for index in range(window + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = ((avg_gain * (window - 1)) + gain) / window
        avg_loss = ((avg_loss * (window - 1)) + loss) / window
        output[index] = _rsi_from_averages(avg_gain, avg_loss)
    return output


def macd(
    values: Sequence[float],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[FeatureSeries, FeatureSeries, FeatureSeries]:
    _validate_window(fast)
    _validate_window(slow)
    _validate_window(signal)
    fast_values = _ema_from_first(values, fast)
    slow_values = _ema_from_first(values, slow)
    line: FeatureSeries = [fast_value - slow_value for fast_value, slow_value in zip(fast_values, slow_values)]
    signal_values = _ema_from_first([float(value) for value in line], signal)
    hist: FeatureSeries = [
        line_value - signal_value for line_value, signal_value in zip(line, signal_values)
    ]
    return line, signal_values, hist


def bollinger_bands(
    values: Sequence[float],
    *,
    window: int = 20,
    stdevs: float = 2.0,
) -> tuple[FeatureSeries, FeatureSeries, FeatureSeries]:
    _validate_window(window)
    middle = sma(values, window)
    upper: FeatureSeries = []
    lower: FeatureSeries = []
    for index, mid in enumerate(middle):
        if mid is None:
            upper.append(None)
            lower.append(None)
            continue
        chunk = values[index + 1 - window : index + 1]
        stdev = math.sqrt(sum((value - mid) ** 2 for value in chunk) / window)
        upper.append(mid + stdevs * stdev)
        lower.append(mid - stdevs * stdev)
    return middle, upper, lower


def atr(bars: Sequence[Bar], window: int) -> FeatureSeries:
    _validate_window(window)
    ranges = true_ranges(bars)
    output: FeatureSeries = []
    current: float | None = None
    for index, value in enumerate(ranges):
        if index + 1 < window:
            output.append(None)
            continue
        if current is None:
            current = sum(ranges[:window]) / window
        else:
            current = ((current * (window - 1)) + value) / window
        output.append(current)
    return output


def true_ranges(bars: Sequence[Bar]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        high_low = float(bar.high) - float(bar.low)
        if previous_close is None:
            ranges.append(high_low)
        else:
            ranges.append(
                max(
                    high_low,
                    abs(float(bar.high) - previous_close),
                    abs(float(bar.low) - previous_close),
                )
            )
        previous_close = float(bar.close)
    return ranges


def vwap(bars: Sequence[Bar]) -> FeatureSeries:
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    output: FeatureSeries = []
    for bar in bars:
        price = float(bar.vwap) if bar.vwap is not None else (bar.high + bar.low + bar.close) / 3.0
        cumulative_price_volume += price * float(bar.volume)
        cumulative_volume += float(bar.volume)
        output.append(cumulative_price_volume / cumulative_volume if cumulative_volume else None)
    return output


def returns(values: Sequence[float], window: int = 1) -> FeatureSeries:
    _validate_window(window)
    output: FeatureSeries = []
    for index, value in enumerate(values):
        if index < window:
            output.append(None)
            continue
        previous = values[index - window]
        output.append((value / previous) - 1.0 if previous else None)
    return output


def volatility(values: Sequence[float], *, window: int = 20, return_window: int = 1) -> FeatureSeries:
    _validate_window(window)
    ret = returns(values, return_window)
    output: FeatureSeries = []
    for index in range(len(ret)):
        chunk = [value for value in ret[max(0, index + 1 - window) : index + 1] if value is not None]
        if len(chunk) < window:
            output.append(None)
            continue
        mean = sum(chunk) / len(chunk)
        output.append(math.sqrt(sum((value - mean) ** 2 for value in chunk) / len(chunk)))
    return output


def volume_ratio(bars: Sequence[Bar], window: int) -> FeatureSeries:
    means = sma(volumes(bars), window)
    output: FeatureSeries = []
    for bar, mean in zip(bars, means):
        if mean is None or mean == 0:
            output.append(None)
        else:
            output.append(float(bar.volume) / mean)
    return output


def _ema_from_first(values: Sequence[float], window: int) -> list[float]:
    _validate_window(window)
    if not values:
        return []
    alpha = 2.0 / (window + 1.0)
    current = float(values[0])
    output = [current]
    for value in values[1:]:
        current = (float(value) - current) * alpha + current
        output.append(current)
    return output


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _validate_window(window: int) -> None:
    if window <= 0:
        raise FeatureError("indicator window must be positive")


def _window(params: dict[str, int | float], *, default: int) -> int:
    window = int(params.get("window", default))
    _validate_window(window)
    return window


__all__ = [
    "BatchIndicator",
    "FeatureSeries",
    "Indicator",
    "atr",
    "bollinger_bands",
    "closes",
    "compute_indicator",
    "ema",
    "highs",
    "lookback_for",
    "lows",
    "macd",
    "output_names_for",
    "required_inputs_for",
    "returns",
    "rsi",
    "sma",
    "true_ranges",
    "volatility",
    "volume_ratio",
    "volumes",
    "vwap",
]
