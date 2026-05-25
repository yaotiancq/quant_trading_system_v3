"""Runtime ML diagnostics helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .types import MLModelManifest


def model_manifest_diagnostics(manifest: MLModelManifest) -> dict[str, Any]:
    """Return a compact, serializable model contract diagnostic payload."""
    return {
        "manifest_id": manifest_id(manifest),
        "manifest_version": manifest.manifest_version,
        "model_id": manifest.model_id,
        "model_type": manifest.model_type,
        "model_artifact": manifest.model_artifact,
        "feature_schema_version": manifest.feature_schema_version,
        "feature_names": list(manifest.feature_names),
        "feature_schema_hash": manifest.feature_schema_hash,
        "stage": manifest.stage,
        "approved_by": manifest.approved_by,
        "approved_at": (
            manifest.approved_at.isoformat().replace("+00:00", "Z")
            if manifest.approved_at is not None
            else None
        ),
        "approval_reason": manifest.approval_reason,
        "created_at": manifest.created_at.isoformat().replace("+00:00", "Z"),
    }


def manifest_id(manifest: MLModelManifest) -> str:
    """Build a stable local manifest identity from model id and schema hash."""
    return f"{manifest.model_id}:{manifest.feature_schema_hash}"


def collect_strategy_ml_diagnostics(strategies: Sequence[Any]) -> list[dict[str, Any]]:
    """Collect loaded ML model diagnostics from strategies that expose them."""
    diagnostics: list[dict[str, Any]] = []
    for strategy in strategies:
        getter = getattr(strategy, "get_model_diagnostics", None)
        if not callable(getter):
            continue
        try:
            details = getter()
        except Exception as exc:  # pragma: no cover - defensive diagnostics boundary
            details = {
                "strategy_id": _strategy_id(strategy),
                "diagnostic_error": str(exc),
            }
        if details:
            diagnostics.append(dict(details))
    return diagnostics


def _strategy_id(strategy: Any) -> str:
    config = getattr(strategy, "config", None)
    strategy_id = getattr(config, "strategy_id", None)
    return str(strategy_id or type(strategy).__name__)


__all__ = ["collect_strategy_ml_diagnostics", "manifest_id", "model_manifest_diagnostics"]
