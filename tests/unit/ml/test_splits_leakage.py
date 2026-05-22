from __future__ import annotations

import unittest
from pathlib import Path

from qts.features import FeaturePipeline, FeatureSpec
from qts.market_data import CSVBarProvider
from qts.ml import (
    MLWorkflowError,
    build_ml_dataset,
    chronological_split,
    validate_no_temporal_leakage,
    validate_split_no_leakage,
    walk_forward_splits,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "market_data" / "ml_directional.csv"


def dataset_samples():
    bars = CSVBarProvider(FIXTURE).get_history(
        ["SPY"],
        "2024-01-02T14:30:00Z",
        "2024-01-02T14:45:00Z",
        "MINUTE",
    )
    pipeline = FeaturePipeline(
        [FeatureSpec("returns", {"window": 1}), FeatureSpec("sma", {"window": 3})],
        schema_version="ml_features_v1",
    )
    return build_ml_dataset(bars, feature_pipeline=pipeline, horizon_bars=1).samples


class MLSplitLeakageTests(unittest.TestCase):
    def test_chronological_split_respects_order_and_embargo(self) -> None:
        split = chronological_split(
            dataset_samples(),
            train_fraction=0.5,
            validation_fraction=0.25,
            test_fraction=0.25,
            embargo_bars=1,
        )

        self.assertLess(split.train[-1].timestamp, split.validation[0].timestamp)
        self.assertLess(split.validation[-1].timestamp, split.test[0].timestamp)
        self.assertTrue(validate_split_no_leakage(split))

    def test_leakage_check_rejects_overlapping_label_horizon(self) -> None:
        samples = dataset_samples()

        with self.assertRaises(MLWorkflowError):
            validate_no_temporal_leakage([samples[0]], [samples[1]])

    def test_walk_forward_splits_are_generated(self) -> None:
        splits = walk_forward_splits(
            dataset_samples(),
            train_window=4,
            validation_window=2,
            step=2,
            embargo_bars=1,
        )

        self.assertGreaterEqual(len(splits), 2)
        self.assertEqual(splits[0].metadata["method"], "walk_forward")
        self.assertLess(splits[0].train[-1].timestamp, splits[0].validation[0].timestamp)


if __name__ == "__main__":
    unittest.main()
