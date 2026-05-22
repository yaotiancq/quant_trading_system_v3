"""Runtime ML inference adapters."""

from __future__ import annotations

from typing import Any

from qts.domain import FeatureFrame, FeatureRecord, ModelPrediction
from qts.features import FeatureSchema

from .models import DirectionalModel
from .registry import FileModelRegistry
from .types import MLWorkflowError


class DefaultMLModelInference:
    """Inference adapter for Phase 7 registered directional models."""

    def __init__(
        self,
        model_uri_or_id: str | None = None,
        *,
        registry: FileModelRegistry | None = None,
    ) -> None:
        self.registry = registry or FileModelRegistry()
        self.model: DirectionalModel | None = None
        if model_uri_or_id is not None:
            self.load_model(model_uri_or_id)

    def load_model(self, model_uri_or_id: str) -> DirectionalModel:
        self.model = self.registry.load_model(model_uri_or_id)
        return self.model

    def predict(
        self,
        feature_data: FeatureRecord | FeatureFrame,
    ) -> ModelPrediction | list[ModelPrediction]:
        model = self._require_model()
        if isinstance(feature_data, FeatureRecord):
            return model.predict_record(feature_data)
        if isinstance(feature_data, FeatureFrame):
            if feature_data.schema_version != model.feature_schema_version:
                raise MLWorkflowError(
                    "feature schema mismatch: "
                    f"model expects {model.feature_schema_version}, got {feature_data.schema_version}"
                )
            predictions: list[ModelPrediction] = []
            for row in feature_data.features:
                record = FeatureRecord(
                    symbol=row["symbol"],
                    timestamp=row["timestamp"],
                    values={name: row.get(name) for name in model.feature_names},
                    schema_version=feature_data.schema_version,
                )
                predictions.append(model.predict_record(record))
            return predictions
        raise MLWorkflowError(f"unsupported feature data type: {type(feature_data).__name__}")

    def get_expected_schema(self) -> FeatureSchema:
        model = self._require_model()
        return FeatureSchema(
            schema_version=model.feature_schema_version,
            feature_names=list(model.feature_names),
        )

    def get_model_metadata(self) -> dict[str, Any]:
        return self._require_model().to_dict()

    def _require_model(self) -> DirectionalModel:
        if self.model is None:
            raise MLWorkflowError("model must be loaded before inference")
        return self.model


__all__ = ["DefaultMLModelInference"]
