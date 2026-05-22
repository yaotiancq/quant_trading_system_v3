from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qts.core import load_mapping_file
from qts.domain import FeatureRecord
from qts.features import FeatureSpec
from qts.market_data import CSVBarProvider
from qts.ml import DefaultMLModelInference, FileModelRegistry, train_directional_pipeline


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs" / "ml" / "directional_baseline.yaml"


class MLTrainingPipelineIntegrationTests(unittest.TestCase):
    def test_training_pipeline_saves_model_and_loaded_model_predicts(self) -> None:
        raw = load_mapping_file(CONFIG)
        market_data = raw["market_data"]
        features = raw["features"]
        labels = raw["labels"]
        splits = raw["splits"]
        bars = CSVBarProvider(market_data["path"]).get_history(
            market_data["symbols"],
            market_data["start"],
            market_data["end"],
            market_data["timeframe"],
        )
        feature_specs = [
            FeatureSpec(item["name"], dict(item.get("parameters") or {}))
            for item in features["specs"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            result = train_directional_pipeline(
                bars,
                model_id="integration-model",
                feature_specs=feature_specs,
                feature_schema_version=features["schema_version"],
                horizon_bars=labels["horizon_bars"],
                up_threshold=labels["up_threshold"],
                down_threshold=labels["down_threshold"],
                train_fraction=splits["train_fraction"],
                validation_fraction=splits["validation_fraction"],
                test_fraction=splits["test_fraction"],
                embargo_bars=splits["embargo_bars"],
                registry=FileModelRegistry(tmp),
            )
            artifact = result["artifact_path"]
            inference = DefaultMLModelInference("integration-model", registry=FileModelRegistry(tmp))
            prediction = inference.predict(
                FeatureRecord(
                    symbol="SPY",
                    timestamp=result["dataset"].samples[-1].timestamp,
                    values=result["dataset"].samples[-1].features,
                    schema_version=result["dataset"].feature_schema_version,
                )
            )
            self.assertTrue(artifact.is_file())

        self.assertEqual(prediction.model_id, "integration-model")
        self.assertIn(prediction.prediction_label, {"UP", "DOWN", "HOLD"})
        self.assertIn("validation", result["metrics"])


if __name__ == "__main__":
    unittest.main()
