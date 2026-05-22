from __future__ import annotations

import unittest
from pathlib import Path

from qts.features import FeaturePipeline, FeatureSpec
from qts.market_data import CSVBarProvider
from qts.ml import build_forward_return_labels, build_ml_dataset


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "market_data" / "ml_directional.csv"


def load_bars():
    return CSVBarProvider(FIXTURE).get_history(
        ["SPY"],
        "2024-01-02T14:30:00Z",
        "2024-01-02T14:45:00Z",
        "MINUTE",
    )


def make_pipeline() -> FeaturePipeline:
    return FeaturePipeline(
        [
            FeatureSpec("returns", {"window": 1}),
            FeatureSpec("sma", {"window": 3}),
        ],
        schema_version="ml_features_v1",
    )


class MLDatasetTests(unittest.TestCase):
    def test_forward_return_labels_capture_up_and_down_moves(self) -> None:
        labels = build_forward_return_labels(load_bars(), horizon_bars=1)
        names = {label.label_name for label in labels.values()}

        self.assertIn("UP", names)
        self.assertIn("DOWN", names)
        self.assertAlmostEqual(labels[("SPY", load_bars()[0].timestamp)].target_return, 0.01)

    def test_build_ml_dataset_reuses_feature_pipeline_and_filters_missing_rows(self) -> None:
        dataset = build_ml_dataset(
            load_bars(),
            feature_pipeline=make_pipeline(),
            horizon_bars=1,
        )

        self.assertEqual(dataset.feature_schema_version, "ml_features_v1")
        self.assertEqual(dataset.feature_names, ["ret_1", "sma_3"])
        self.assertEqual(dataset.symbols, ["SPY"])
        self.assertGreater(len(dataset.samples), 8)
        self.assertEqual(dataset.samples[0].timestamp.isoformat(), "2024-01-02T14:32:00+00:00")
        self.assertIn(dataset.samples[0].label_name, {"UP", "DOWN", "HOLD"})
        self.assertIn("ret_1", dataset.samples[0].features)
        self.assertIn("sma_3", dataset.samples[0].features)


if __name__ == "__main__":
    unittest.main()
