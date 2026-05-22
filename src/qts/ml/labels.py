"""Label generation for offline ML datasets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from qts.domain import Bar

from .types import ForwardReturnLabel, MLWorkflowError


def build_forward_return_labels(
    bars: Sequence[Bar],
    *,
    horizon_bars: int = 1,
    up_threshold: float = 0.0,
    down_threshold: float = 0.0,
) -> dict[tuple[str, object], ForwardReturnLabel]:
    """Build UP/DOWN/HOLD labels from future close returns."""
    if horizon_bars <= 0:
        raise MLWorkflowError("horizon_bars must be positive")
    if up_threshold < 0 or down_threshold < 0:
        raise MLWorkflowError("label thresholds must be non-negative")

    by_symbol: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        by_symbol[bar.symbol].append(bar)

    labels: dict[tuple[str, object], ForwardReturnLabel] = {}
    for symbol, symbol_bars in by_symbol.items():
        ordered = sorted(symbol_bars, key=lambda bar: bar.timestamp)
        for index, bar in enumerate(ordered):
            future_index = index + horizon_bars
            if future_index >= len(ordered):
                continue
            future_bar = ordered[future_index]
            if bar.close <= 0:
                raise MLWorkflowError(f"cannot label non-positive close for {symbol}")
            target_return = (future_bar.close - bar.close) / bar.close
            if target_return > up_threshold:
                label = 1
            elif target_return < -down_threshold:
                label = -1
            else:
                label = 0
            labels[(symbol, bar.timestamp)] = ForwardReturnLabel(
                symbol=symbol,
                timestamp=bar.timestamp,
                label_end_timestamp=future_bar.timestamp,
                current_close=bar.close,
                future_close=future_bar.close,
                target_return=target_return,
                label=label,
                horizon_bars=horizon_bars,
            )
    return labels


__all__ = ["build_forward_return_labels"]
