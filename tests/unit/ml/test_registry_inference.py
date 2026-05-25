from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from qts.domain import FeatureRecord
from qts.ml import (
    DefaultMLModelInference,
    DirectionalModel,
    FileModelRegistry,
    MLWorkflowError,
    build_feature_schema_hash,
)


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_model() -> DirectionalModel:
    return DirectionalModel(
        model_id="unit-model",
        feature_names=["ret_1"],
        feature_schema_version="ml_features_v1",
        weights={"ret_1": 100.0},
        feature_means={"ret_1": 0.0},
        decision_threshold=0.55,
        metadata={"horizon": "next_1_bars"},
    )


class RegistryInferenceTests(unittest.TestCase):
    def test_registry_round_trips_model_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            path = registry.save_model(make_model())
            manifest = registry.load_manifest("unit-model")
            loaded = registry.load_model("unit-model")

        self.assertEqual(path.name, "model.json")
        self.assertEqual(manifest.model_artifact, "model.json")
        self.assertEqual(manifest.stage, "candidate")
        self.assertEqual(
            manifest.feature_schema_hash,
            build_feature_schema_hash("ml_features_v1", ["ret_1"]),
        )
        self.assertEqual(loaded.model_id, "unit-model")
        self.assertEqual(loaded.feature_names, ["ret_1"])

    def test_registry_rejects_manifest_model_contract_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())
            manifest_path = Path(tmp) / "unit-model" / "manifest.json"
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_data["feature_names"] = ["different_feature"]
            manifest_data["feature_schema_hash"] = build_feature_schema_hash(
                "ml_features_v1",
                ["different_feature"],
            )
            manifest_path.write_text(
                json.dumps(manifest_data, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MLWorkflowError, "manifest does not match"):
                registry.load_model("unit-model")

    def test_registry_rejects_model_artifact_schema_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())
            model_path = Path(tmp) / "unit-model" / "model.json"
            model_data = json.loads(model_path.read_text(encoding="utf-8"))
            model_data["feature_schema_hash"] = "bad-hash"
            model_path.write_text(
                json.dumps(model_data, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MLWorkflowError, "feature_schema_hash"):
                registry.load_model("unit-model")

    def test_registry_transitions_model_stage_with_approval_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())

            validated = registry.mark_validated("unit-model", actor="research", reason="metrics reviewed")
            approved = registry.approve_model("unit-model", approved_by="risk", reason="paper validation")
            archived = registry.archive_model("unit-model", actor="risk", reason="superseded")
            reloaded = registry.load_manifest("unit-model")

        self.assertEqual(validated.stage, "validated")
        self.assertEqual(approved.stage, "approved")
        self.assertEqual(approved.approved_by, "risk")
        self.assertIsNotNone(approved.approved_at)
        self.assertEqual(approved.approval_reason, "paper validation")
        self.assertEqual(archived.stage, "archived")
        self.assertEqual(reloaded.stage, "archived")
        self.assertEqual(len(reloaded.stage_history), 3)
        self.assertEqual(reloaded.stage_history[-1]["from_stage"], "approved")
        self.assertEqual(reloaded.stage_history[-1]["to_stage"], "archived")

    def test_registry_rejects_approval_without_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())

            with self.assertRaisesRegex(MLWorkflowError, "approved_by"):
                registry.transition_model_stage("unit-model", "approved")

    def test_inference_returns_model_prediction_and_enforces_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())
            inference = DefaultMLModelInference("unit-model", registry=registry)

            prediction = inference.predict(
                FeatureRecord(
                    symbol="SPY",
                    timestamp=NOW,
                    values={"ret_1": 0.02},
                    schema_version="ml_features_v1",
                )
            )

            self.assertEqual(prediction.prediction_label, "UP")
            self.assertGreater(prediction.probability, 0.55)
            self.assertEqual(inference.get_expected_schema().feature_names, ["ret_1"])
            self.assertEqual(inference.get_model_manifest().model_id, "unit-model")
            self.assertEqual(
                inference.get_model_manifest().feature_schema_hash,
                prediction.metadata["feature_schema_hash"],
            )

            with self.assertRaises(MLWorkflowError):
                inference.predict(
                    FeatureRecord(
                        symbol="SPY",
                        timestamp=NOW,
                        values={"ret_1": 0.02},
                        schema_version="wrong_schema",
                    )
                )

    def test_inference_enforces_approved_model_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())

            with self.assertRaisesRegex(MLWorkflowError, "requires approved"):
                DefaultMLModelInference(
                    "unit-model",
                    registry=registry,
                    require_approved_model=True,
                )

            registry.approve_model("unit-model", approved_by="risk", reason="accepted")
            approved = DefaultMLModelInference(
                "unit-model",
                registry=registry,
                require_approved_model=True,
            )
            self.assertEqual(approved.get_model_manifest().stage, "approved")

            registry.archive_model("unit-model", actor="risk", reason="retired")
            with self.assertRaisesRegex(MLWorkflowError, "requires approved"):
                DefaultMLModelInference(
                    "unit-model",
                    registry=registry,
                    require_approved_model=True,
                )

    def test_inference_enforces_allowed_model_stages_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileModelRegistry(tmp)
            registry.save_model(make_model())

            candidate = DefaultMLModelInference(
                "unit-model",
                registry=registry,
                allowed_model_stages=["candidate", "validated"],
            )
            self.assertEqual(candidate.get_model_manifest().stage, "candidate")

            with self.assertRaisesRegex(MLWorkflowError, "not allowed"):
                DefaultMLModelInference(
                    "unit-model",
                    registry=registry,
                    allowed_model_stages=["approved"],
                )


if __name__ == "__main__":
    unittest.main()
