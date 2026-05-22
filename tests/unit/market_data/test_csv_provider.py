from __future__ import annotations

import unittest
from datetime import timezone
from pathlib import Path

from qts.core import DataError
from qts.domain import BarTimeframe
from qts.features import FeaturePipeline, FeatureSpec
from qts.market_data import CSVBarProvider, DefaultDataPortal


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "market_data"


class CSVBarProviderTests(unittest.TestCase):
    def test_loads_and_normalizes_csv_bars(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")

        bars = provider.get_history(
            ["spy"],
            "2024-01-02T14:30:00Z",
            "2024-01-02T14:35:00Z",
            BarTimeframe.MINUTE,
        )

        self.assertEqual(len(bars), 6)
        self.assertEqual(bars[0].symbol, "SPY")
        self.assertEqual(bars[0].timestamp.tzinfo, timezone.utc)
        self.assertEqual(bars[-1].close, 110)

    def test_missing_required_bar_column_fails(self) -> None:
        with self.assertRaises(DataError):
            CSVBarProvider(FIXTURES / "bars_missing_column.csv")

    def test_duplicate_symbol_timestamp_timeframe_fails(self) -> None:
        with self.assertRaises(DataError):
            CSVBarProvider(FIXTURES / "bars_duplicate.csv")

    def test_iter_replay_is_deterministic(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")

        events = list(
            provider.iter_replay(
                ["SPY", "QQQ"],
                "2024-01-02T14:30:00Z",
                "2024-01-02T14:31:00Z",
                "MINUTE",
            )
        )

        self.assertEqual(
            [(event.timestamp.isoformat(), event.symbol) for event in events],
            [
                ("2024-01-02T14:30:00+00:00", "QQQ"),
                ("2024-01-02T14:30:00+00:00", "SPY"),
                ("2024-01-02T14:31:00+00:00", "QQQ"),
                ("2024-01-02T14:31:00+00:00", "SPY"),
            ],
        )
        self.assertEqual(provider.get_latest_bar("spy"), events[-1])


class DataPortalTests(unittest.TestCase):
    def test_portal_exposes_history_current_bar_and_feature_frame(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")
        pipeline = FeaturePipeline(
            [FeatureSpec("sma", {"window": 3}), FeatureSpec("returns", {"window": 1})]
        )
        portal = DefaultDataPortal(
            provider,
            symbols=["SPY"],
            start="2024-01-02T14:30:00Z",
            end="2024-01-02T14:35:00Z",
            timeframe="MINUTE",
            feature_pipeline=pipeline,
        )

        bars = portal.get_bars("spy", lookback=2)
        portal.advance(bars[-1])
        frame = portal.get_feature_frame(["SPY"], feature_names=["sma_3"], lookback=4)

        self.assertEqual([bar.close for bar in bars], [108, 110])
        self.assertEqual(portal.get_current_bar("SPY"), bars[-1])
        self.assertEqual(frame.features[-1]["sma_3"], 108)
        self.assertNotIn("ret_1", frame.features[-1])

    def test_replay_bounded_portal_does_not_expose_future_bars(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")
        portal = DefaultDataPortal(
            provider,
            symbols=["SPY"],
            start="2024-01-02T14:30:00Z",
            end="2024-01-02T14:35:00Z",
            timeframe="MINUTE",
            enforce_replay_bounds=True,
        )
        bars = provider.get_history(
            ["SPY"],
            "2024-01-02T14:30:00Z",
            "2024-01-02T14:35:00Z",
            "MINUTE",
        )

        self.assertEqual(portal.get_bars("SPY"), [])

        portal.advance(bars[0])
        self.assertEqual(portal.get_bars("SPY"), [bars[0]])
        self.assertEqual(portal.get_bars("SPY", end="2024-01-02T14:35:00Z"), [bars[0]])

        portal.advance(bars[1])
        self.assertEqual(portal.get_bars("SPY", lookback=2), bars[:2])


if __name__ == "__main__":
    unittest.main()
