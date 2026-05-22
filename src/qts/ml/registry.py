"""Filesystem model registry for Phase 7."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DirectionalModel
from .types import MLWorkflowError


class FileModelRegistry:
    """Save and load model artifacts from a local directory."""

    def __init__(self, root_dir: str | Path = "artifacts/models") -> None:
        self.root_dir = Path(root_dir)

    def save_model(self, model: DirectionalModel) -> Path:
        model_dir = self.root_dir / model.model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        path = model_dir / "model.json"
        path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load_model(self, model_id_or_uri: str | Path) -> DirectionalModel:
        path = self._resolve_model_path(model_id_or_uri)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MLWorkflowError(f"invalid model artifact JSON: {path}") from exc
        if data.get("model_type") != "directional_linear_v1":
            raise MLWorkflowError(f"unsupported model type: {data.get('model_type')}")
        return DirectionalModel.from_dict(dict(data))

    def load_metadata(self, model_id_or_uri: str | Path) -> dict[str, Any]:
        return self.load_model(model_id_or_uri).to_dict()

    def _resolve_model_path(self, model_id_or_uri: str | Path) -> Path:
        candidate = Path(model_id_or_uri)
        if candidate.is_dir():
            candidate = candidate / "model.json"
        elif not candidate.exists():
            candidate = self.root_dir / str(model_id_or_uri) / "model.json"
        if not candidate.is_file():
            raise MLWorkflowError(f"model artifact does not exist: {candidate}")
        return candidate


__all__ = ["FileModelRegistry"]
