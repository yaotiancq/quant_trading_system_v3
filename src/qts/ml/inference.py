"""Runtime ML inference adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qts.domain import FeatureFrame, FeatureRecord, ModelPrediction
from qts.features import FeatureSchema

from .models import DirectionalModel
from .registry import FileModelRegistry
from .types import MLModelManifest, MLWorkflowError, normalize_model_stage


class DefaultMLModelInference:
    """Inference adapter for Phase 7 registered directional models."""

    def __init__(
        self,
        model_uri_or_id: str | None = None,
        *,
        registry: FileModelRegistry | None = None,
        require_approved_model: bool = False,
        allowed_model_stages: Sequence[str] | None = None,
    ) -> None:
        self.registry = registry or FileModelRegistry()
        self.require_approved_model = bool(require_approved_model)
        self.allowed_model_stages = _normalize_allowed_stages(
            allowed_model_stages,
            require_approved_model=self.require_approved_model,
        )
        self.model: DirectionalModel | None = None
        self.manifest: MLModelManifest | None = None
        if model_uri_or_id is not None:
            self.load_model(model_uri_or_id)

    def load_model(self, model_uri_or_id: str) -> DirectionalModel:
        self.model = self.registry.load_model(model_uri_or_id)
        self.manifest = self.registry.manifest_for_model(model_uri_or_id)
        self.registry.validate_model_contract(self.model, self.manifest)
        self._validate_stage_policy(self.manifest)
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

    def get_model_manifest(self) -> MLModelManifest:
        self._require_model()
        if self.manifest is None:
            raise MLWorkflowError("model manifest must be loaded before inference")
        return self.manifest

    def _require_model(self) -> DirectionalModel:
        if self.model is None:
            raise MLWorkflowError("model must be loaded before inference")
        return self.model

    def _validate_stage_policy(self, manifest: MLModelManifest) -> None:
        if self.require_approved_model and manifest.stage != "approved":
            raise MLWorkflowError(
                "model stage policy requires approved model; "
                f"{manifest.model_id} is {manifest.stage}"
            )
        if self.allowed_model_stages is not None and manifest.stage not in self.allowed_model_stages:
            allowed = ", ".join(sorted(self.allowed_model_stages))
            raise MLWorkflowError(
                f"model stage {manifest.stage} is not allowed for {manifest.model_id}; "
                f"allowed stages: {allowed}"
            )


def _normalize_allowed_stages(
    allowed_model_stages: Sequence[str] | None,
    *,
    require_approved_model: bool,
) -> set[str] | None:
    if allowed_model_stages is None:
        return None
    if isinstance(allowed_model_stages, (str, bytes, bytearray)):
        raise MLWorkflowError("allowed_model_stages must be a sequence of stage names")
    stages = {normalize_model_stage(str(stage)) for stage in allowed_model_stages}
    if not stages:
        raise MLWorkflowError("allowed_model_stages must not be empty")
    if require_approved_model and "approved" not in stages:
        raise MLWorkflowError("require_approved_model requires approved in allowed_model_stages")
    return stages


__all__ = ["DefaultMLModelInference"]
