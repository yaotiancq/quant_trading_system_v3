from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from qts.domain import FeatureRecord
from qts.ml import (
    DefaultMLModelInference,
    DirectionalModel,
    FileModelRegistry,
    MLWorkflowError,
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
            loaded = registry.load_model("unit-model")

        self.assertEqual(path.name, "model.json")
        self.assertEqual(loaded.model_id, "unit-model")
        self.assertEqual(loaded.feature_names, ["ret_1"])

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

            with self.assertRaises(MLWorkflowError):
                inference.predict(
                    FeatureRecord(
                        symbol="SPY",
                        timestamp=NOW,
                        values={"ret_1": 0.02},
                        schema_version="wrong_schema",
                    )
                )


if __name__ == "__main__":
    unittest.main()
