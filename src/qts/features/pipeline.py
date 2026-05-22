"""Feature schema and pipeline implementation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from qts.core import FeatureError
from qts.domain import Bar, FeatureFrame, FeatureRecord, normalize_symbol

from .indicators import compute_indicator, output_names_for


@dataclass(frozen=True)
class FeatureSpec:
    """One configured feature calculation."""

    name: str
    parameters: dict[str, int | float] = field(default_factory=dict)

    @property
    def output_names(self) -> list[str]:
        return output_names_for(self.name, self.parameters)


@dataclass(frozen=True)
class FeatureSchema:
    """Expected feature output schema."""

    schema_version: str
    feature_names: list[str]

    def validate_frame(self, frame: FeatureFrame) -> bool:
        if frame.schema_version != self.schema_version:
            raise FeatureError(
                f"feature schema version mismatch: expected {self.schema_version}, "
                f"got {frame.schema_version}"
            )
        for row_index, row in enumerate(frame.features, start=1):
            missing = [name for name in self.feature_names if name not in row]
            if missing:
                raise FeatureError(
                    f"missing features on row {row_index}: {', '.join(sorted(missing))}"
                )
        return True


class FeaturePipeline:
    """Batch-first feature pipeline for normalized bars."""

    def __init__(
        self,
        specs: Sequence[FeatureSpec | dict[str, Any]] | None = None,
        *,
        schema_version: str = "features_v1",
        source: str = "feature_pipeline",
    ) -> None:
        self.specs = [_coerce_spec(spec) for spec in (specs or default_feature_specs())]
        self.schema_version = schema_version
        self.source = source
        self._online_bars: list[Bar] = []

    def fit(self, historical_data: Sequence[Bar], labels: Any | None = None) -> "FeaturePipeline":
        return self

    def transform_batch(self, historical_bars: Sequence[Bar]) -> FeatureFrame:
        bars = sorted(list(historical_bars), key=lambda bar: (bar.symbol, bar.timestamp))
        if not bars:
            raise FeatureError("cannot compute features for an empty bar sequence")

        rows: list[dict[str, Any]] = []
        by_symbol: dict[str, list[Bar]] = defaultdict(list)
        for bar in bars:
            by_symbol[bar.symbol].append(bar)

        for symbol in sorted(by_symbol):
            symbol_bars = by_symbol[symbol]
            computed: dict[str, list[float | None]] = {}
            for spec in self.specs:
                computed.update(compute_indicator(spec.name, symbol_bars, spec.parameters))
            for index, bar in enumerate(symbol_bars):
                row: dict[str, Any] = {"symbol": bar.symbol, "timestamp": bar.timestamp}
                for feature_name, series in computed.items():
                    row[feature_name] = series[index]
                rows.append(row)

        rows.sort(key=lambda row: (row["timestamp"], row["symbol"]))
        return FeatureFrame(
            symbols=sorted({row["symbol"] for row in rows}),
            timestamps=[row["timestamp"] for row in rows],
            features=rows,
            schema_version=self.schema_version,
            generated_at=datetime.now(timezone.utc),
            source=self.source,
        )

    def update_online(self, new_market_event: Bar) -> FeatureRecord:
        if not isinstance(new_market_event, Bar):
            raise FeatureError("online feature updates currently require Bar events")
        self._online_bars.append(new_market_event)
        frame = self.transform_batch(
            [bar for bar in self._online_bars if bar.symbol == new_market_event.symbol]
        )
        latest = frame.features[-1]
        values = {key: value for key, value in latest.items() if key not in {"symbol", "timestamp"}}
        return FeatureRecord(
            symbol=new_market_event.symbol,
            timestamp=new_market_event.timestamp,
            values=values,
            schema_version=self.schema_version,
        )

    def get_schema(self) -> FeatureSchema:
        feature_names: list[str] = []
        for spec in self.specs:
            feature_names.extend(spec.output_names)
        return FeatureSchema(schema_version=self.schema_version, feature_names=feature_names)

    def validate_schema(self, feature_data: FeatureFrame) -> bool:
        return self.get_schema().validate_frame(feature_data)

    def reset_online(self) -> None:
        self._online_bars.clear()


def default_feature_specs() -> list[FeatureSpec]:
    return [
        FeatureSpec("sma", {"window": 20}),
        FeatureSpec("ema", {"window": 20}),
        FeatureSpec("rsi", {"window": 14}),
        FeatureSpec("returns", {"window": 1}),
        FeatureSpec("volatility", {"window": 20}),
    ]


def _coerce_spec(spec: FeatureSpec | dict[str, Any]) -> FeatureSpec:
    if isinstance(spec, FeatureSpec):
        return spec
    if isinstance(spec, dict):
        return FeatureSpec(name=str(spec["name"]), parameters=dict(spec.get("parameters") or {}))
    raise FeatureError(f"unsupported feature spec type: {type(spec).__name__}")


__all__ = [
    "FeaturePipeline",
    "FeatureSchema",
    "FeatureSpec",
    "default_feature_specs",
]
