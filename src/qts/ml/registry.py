"""Filesystem model registry with manifest contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DirectionalModel
from .types import MLModelManifest, MLWorkflowError, build_feature_schema_hash, normalize_model_stage


class FileModelRegistry:
    """Save and load model artifacts from a local directory."""

    def __init__(self, root_dir: str | Path = "artifacts/models") -> None:
        self.root_dir = Path(root_dir)

    def save_model(
        self,
        model: DirectionalModel,
        *,
        stage: str = "candidate",
        manifest_metadata: dict[str, Any] | None = None,
        approved_by: str | None = None,
        approval_reason: str | None = None,
    ) -> Path:
        model_dir = self.root_dir / model.model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        path = model_dir / "model.json"
        path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        try:
            manifest = MLModelManifest.from_model(
                model,
                model_artifact=path.name,
                stage=stage,
                metadata=manifest_metadata,
                approved_by=approved_by,
                approval_reason=approval_reason,
            )
        except ValueError as exc:
            raise MLWorkflowError(f"invalid model manifest contract: {exc}") from exc
        self.save_manifest(manifest)
        return path

    def load_model(self, model_id_or_uri: str | Path) -> DirectionalModel:
        path = self._resolve_model_path(model_id_or_uri)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MLWorkflowError(f"invalid model artifact JSON: {path}") from exc
        if data.get("model_type") != "directional_linear_v1":
            raise MLWorkflowError(f"unsupported model type: {data.get('model_type')}")
        model = DirectionalModel.from_dict(dict(data))
        manifest_path = self._manifest_path(path.parent)
        if manifest_path.exists():
            self.validate_model_contract(model, self.load_manifest(path.parent))
        return model

    def load_metadata(self, model_id_or_uri: str | Path) -> dict[str, Any]:
        return self.load_model(model_id_or_uri).to_dict()

    def save_manifest(self, manifest: MLModelManifest) -> Path:
        model_dir = self.root_dir / manifest.model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        return self._write_manifest(manifest, model_dir)

    def load_manifest(self, model_id_or_uri: str | Path) -> MLModelManifest:
        model_dir = self._resolve_model_dir(model_id_or_uri)
        path = self._manifest_path(model_dir)
        if not path.is_file():
            raise MLWorkflowError(f"model manifest does not exist: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MLWorkflowError(f"invalid model manifest JSON: {path}") from exc
        try:
            return MLModelManifest.from_dict(dict(data))
        except (KeyError, TypeError, ValueError) as exc:
            raise MLWorkflowError(f"invalid model manifest contract: {path}: {exc}") from exc

    def manifest_for_model(self, model_id_or_uri: str | Path) -> MLModelManifest:
        """Return the saved manifest, or synthesize a legacy one for old artifacts."""
        path = self._resolve_model_path(model_id_or_uri)
        try:
            return self.load_manifest(path.parent)
        except MLWorkflowError as exc:
            if "model manifest does not exist" not in str(exc):
                raise
        model = self.load_model(path)
        return MLModelManifest.from_model(
            model,
            model_artifact=path.name,
            stage="legacy",
            metadata={"legacy_manifest": True},
        )

    def transition_model_stage(
        self,
        model_id_or_uri: str | Path,
        stage: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
        approved_by: str | None = None,
        approval_reason: str | None = None,
    ) -> MLModelManifest:
        """Transition a model manifest to a governance stage and persist it."""
        target_stage = normalize_model_stage(stage, allow_legacy=False)
        path = self._resolve_model_path(model_id_or_uri)
        model = self.load_model(path)
        manifest = self.manifest_for_model(path)
        self.validate_model_contract(model, manifest)
        try:
            updated = manifest.with_stage(
                target_stage,
                actor=actor,
                reason=reason,
                approved_by=approved_by,
                approval_reason=approval_reason,
            )
        except ValueError as exc:
            raise MLWorkflowError(f"invalid model stage transition: {exc}") from exc
        self._write_manifest(updated, path.parent)
        return updated

    def mark_candidate(
        self,
        model_id_or_uri: str | Path,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> MLModelManifest:
        return self.transition_model_stage(
            model_id_or_uri,
            "candidate",
            actor=actor,
            reason=reason,
        )

    def mark_validated(
        self,
        model_id_or_uri: str | Path,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> MLModelManifest:
        return self.transition_model_stage(
            model_id_or_uri,
            "validated",
            actor=actor,
            reason=reason,
        )

    def approve_model(
        self,
        model_id_or_uri: str | Path,
        *,
        approved_by: str,
        reason: str | None = None,
    ) -> MLModelManifest:
        return self.transition_model_stage(
            model_id_or_uri,
            "approved",
            actor=approved_by,
            reason=reason,
            approved_by=approved_by,
            approval_reason=reason,
        )

    def archive_model(
        self,
        model_id_or_uri: str | Path,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> MLModelManifest:
        return self.transition_model_stage(
            model_id_or_uri,
            "archived",
            actor=actor,
            reason=reason,
        )

    def validate_model_contract(
        self,
        model: DirectionalModel,
        manifest: MLModelManifest,
    ) -> None:
        expected_hash = build_feature_schema_hash(
            model.feature_schema_version,
            model.feature_names,
        )
        mismatches: list[str] = []
        if manifest.model_id != model.model_id:
            mismatches.append("model_id")
        if manifest.model_type != model.to_dict().get("model_type"):
            mismatches.append("model_type")
        if manifest.feature_schema_version != model.feature_schema_version:
            mismatches.append("feature_schema_version")
        if manifest.feature_names != model.feature_names:
            mismatches.append("feature_names")
        if manifest.feature_schema_hash != expected_hash:
            mismatches.append("feature_schema_hash")
        if mismatches:
            raise MLWorkflowError(
                "model manifest does not match model artifact: " + ", ".join(mismatches)
            )

    def _resolve_model_path(self, model_id_or_uri: str | Path) -> Path:
        candidate = Path(model_id_or_uri)
        if candidate.is_dir():
            candidate = candidate / "model.json"
        elif not candidate.exists():
            candidate = self.root_dir / str(model_id_or_uri) / "model.json"
        if not candidate.is_file():
            raise MLWorkflowError(f"model artifact does not exist: {candidate}")
        return candidate

    def _resolve_model_dir(self, model_id_or_uri: str | Path) -> Path:
        candidate = Path(model_id_or_uri)
        if candidate.is_file():
            return candidate.parent
        if candidate.is_dir():
            return candidate
        model_dir = self.root_dir / str(model_id_or_uri)
        if model_dir.is_dir():
            return model_dir
        return candidate

    def _manifest_path(self, model_dir: Path) -> Path:
        return model_dir / "manifest.json"

    def _write_manifest(self, manifest: MLModelManifest, model_dir: Path) -> Path:
        model_dir.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path(model_dir)
        path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path


__all__ = ["FileModelRegistry"]
