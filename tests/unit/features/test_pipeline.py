from __future__ import annotations

import unittest
from pathlib import Path

from qts.core import FeatureError
from qts.features import FeaturePipeline, FeatureSpec
from qts.market_data import CSVBarProvider


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "market_data"


class FeaturePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")
        self.bars = provider.get_history(
            ["SPY"],
            "2024-01-02T14:30:00Z",
            "2024-01-02T14:35:00Z",
            "MINUTE",
        )

    def test_pipeline_outputs_schema_valid_feature_frame(self) -> None:
        pipeline = FeaturePipeline(
            [
                FeatureSpec("sma", {"window": 3}),
                FeatureSpec("ema", {"window": 3}),
                FeatureSpec("rsi", {"window": 3}),
                FeatureSpec("returns", {"window": 1}),
                FeatureSpec("volatility", {"window": 3}),
            ],
            schema_version="test_schema_v1",
        )

        frame = pipeline.transform_batch(self.bars)

        self.assertEqual(frame.schema_version, "test_schema_v1")
        self.assertEqual(frame.symbols, ["SPY"])
        self.assertEqual(frame.features[-1]["sma_3"], 108)
        self.assertIn("vol_3", frame.features[-1])
        self.assertTrue(pipeline.validate_schema(frame))

    def test_update_online_returns_latest_feature_record(self) -> None:
        pipeline = FeaturePipeline([FeatureSpec("sma", {"window": 3})])

        latest = None
        for bar in self.bars:
            latest = pipeline.update_online(bar)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.symbol, "SPY")
        self.assertEqual(latest.values["sma_3"], 108)

    def test_schema_validation_fails_for_missing_feature(self) -> None:
        pipeline = FeaturePipeline(
            [FeatureSpec("sma", {"window": 3}), FeatureSpec("ema", {"window": 3})]
        )
        frame = pipeline.transform_batch(self.bars)
        for row in frame.features:
            row.pop("ema_3")

        with self.assertRaises(FeatureError):
            pipeline.validate_schema(frame)


if __name__ == "__main__":
    unittest.main()
