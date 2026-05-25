"""Runtime ML strategy adapters."""

from __future__ import annotations

from typing import Any

from qts.core import StrategyError
from qts.domain import (
    Bar,
    FeatureFrame,
    FeatureRecord,
    ModelPrediction,
    PortfolioSnapshot,
    Signal,
    SignalDirection,
    StrategyConfig,
)
from qts.ml import DefaultMLModelInference, FileModelRegistry, MLWorkflowError

from .base import BaseStrategy


class MLSignalStrategy(BaseStrategy):
    """Convert registered model predictions into normalized signals."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        super().__init__(config)
        self.inference: DefaultMLModelInference | None = None

    def initialize(self, strategy_config: StrategyConfig, data_portal: Any, context: Any = None) -> None:
        super().initialize(strategy_config, data_portal, context)
        params = self.parameters
        model_uri = params.get("model_uri") or params.get("model_id")
        if not model_uri:
            raise StrategyError("ML strategy requires model_uri or model_id")
        registry_dir = params.get("registry_dir", "artifacts/models")
        try:
            self.inference = DefaultMLModelInference(
                str(model_uri),
                registry=FileModelRegistry(str(registry_dir)),
                require_approved_model=bool(params.get("require_approved_model", False)),
                allowed_model_stages=params.get("allowed_model_stages"),
            )
        except MLWorkflowError as exc:
            raise StrategyError(str(exc)) from exc
        self._validate_runtime_feature_schema(data_portal)

    def on_data(
        self,
        market_event: Bar,
        features: FeatureRecord | FeatureFrame | dict[str, Any] | None,
        portfolio_snapshot: PortfolioSnapshot | None = None,
    ) -> list[Signal]:
        self._validate_symbol(market_event.symbol)
        if features is None:
            return []
        inference = self._require_inference()
        try:
            prediction = inference.predict(features)  # type: ignore[arg-type]
        except MLWorkflowError as exc:
            raise StrategyError(str(exc)) from exc
        selected = _select_prediction(prediction, market_event.symbol)
        if selected is None:
            return []

        probability = selected.probability
        if probability is None:
            return []
        buy_threshold = float(self.parameters.get("buy_probability_threshold", 0.55))
        sell_threshold = float(self.parameters.get("sell_probability_threshold", 0.45))
        emit_hold = bool(self.parameters.get("emit_hold", False))

        if str(selected.prediction_label) == "UP" and probability >= buy_threshold:
            direction = SignalDirection.BUY
        elif str(selected.prediction_label) == "DOWN" and probability <= sell_threshold:
            direction = SignalDirection.SELL
        elif emit_hold:
            direction = SignalDirection.HOLD
        else:
            return []

        confidence = max(probability, 1.0 - probability)
        strength = min(abs(probability - 0.5) * 2.0, 1.0)
        model_diagnostics = inference.get_model_diagnostics()
        return [
            Signal(
                signal_id=_signal_id(self.name, market_event, selected),
                strategy_id=self.name,
                symbol=market_event.symbol,
                timestamp=market_event.timestamp,
                direction=direction,
                strength=strength,
                confidence=confidence,
                reason="ml_directional_prediction",
                metadata={
                    "prediction": selected.to_dict(),
                    "model_manifest": model_diagnostics,
                    "manifest_id": model_diagnostics["manifest_id"],
                    "manifest_stage": model_diagnostics["stage"],
                    "manifest_feature_schema_hash": model_diagnostics[
                        "feature_schema_hash"
                    ],
                },
            )
        ]

    def get_model_diagnostics(self) -> dict[str, Any]:
        inference = self._require_inference()
        return {
            "strategy_id": self.name,
            "strategy_type": self.config.strategy_type if self.config else "ml_directional",
            **inference.get_model_diagnostics(),
        }

    def _require_inference(self) -> DefaultMLModelInference:
        if self.inference is None:
            raise StrategyError("ML strategy must be initialized before use")
        return self.inference

    def _validate_runtime_feature_schema(self, data_portal: Any) -> None:
        inference = self._require_inference()
        feature_pipeline = getattr(data_portal, "feature_pipeline", None)
        if feature_pipeline is None or not hasattr(feature_pipeline, "get_schema"):
            return
        expected = inference.get_expected_schema()
        actual = feature_pipeline.get_schema()
        if actual.schema_version != expected.schema_version:
            raise StrategyError(
                "ML strategy feature schema mismatch: "
                f"model expects {expected.schema_version}, got {actual.schema_version}"
            )
        missing = [name for name in expected.feature_names if name not in actual.feature_names]
        if missing:
            raise StrategyError(
                "ML strategy feature schema is missing expected features: "
                f"{', '.join(sorted(missing))}"
            )


def _select_prediction(
    prediction: ModelPrediction | list[ModelPrediction],
    symbol: str,
) -> ModelPrediction | None:
    if isinstance(prediction, ModelPrediction):
        return prediction if prediction.symbol == symbol else None
    matching = [item for item in prediction if item.symbol == symbol]
    return matching[-1] if matching else None


def _signal_id(strategy_id: str, bar: Bar, prediction: ModelPrediction) -> str:
    timestamp = bar.timestamp.strftime("%Y%m%dT%H%M%SZ")
    label = str(prediction.prediction_label).lower()
    return f"{strategy_id}-{bar.symbol}-{timestamp}-ml-{label}"


__all__ = ["MLSignalStrategy"]
