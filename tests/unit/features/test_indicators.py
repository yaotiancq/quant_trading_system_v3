from __future__ import annotations

import unittest
from pathlib import Path

from qts.features import atr, ema, returns, rsi, sma, volatility, volume_ratio, vwap
from qts.market_data import CSVBarProvider


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "market_data"


class IndicatorTests(unittest.TestCase):
    def setUp(self) -> None:
        provider = CSVBarProvider(FIXTURES / "bars.csv")
        self.bars = provider.get_history(
            ["SPY"],
            "2024-01-02T14:30:00Z",
            "2024-01-02T14:35:00Z",
            "MINUTE",
        )
        self.closes = [bar.close for bar in self.bars]

    def test_sma_known_values(self) -> None:
        self.assertEqual(sma(self.closes, 3), [None, None, 102.0, 104.0, 106.0, 108.0])

    def test_ema_known_values(self) -> None:
        self.assertEqual(ema(self.closes, 3), [None, None, 102.0, 104.0, 106.0, 108.0])

    def test_rsi_for_monotonic_gains_is_100_after_window(self) -> None:
        self.assertEqual(rsi(self.closes, 3), [None, None, None, 100.0, 100.0, 100.0])

    def test_returns_known_values(self) -> None:
        output = returns(self.closes, 1)

        self.assertIsNone(output[0])
        self.assertAlmostEqual(output[1], 0.02)
        self.assertAlmostEqual(output[-1], (110 / 108) - 1.0)

    def test_volatility_known_constant_returns(self) -> None:
        output = volatility([100, 110, 121, 133.1], window=2)

        self.assertIsNone(output[0])
        self.assertIsNone(output[1])
        self.assertAlmostEqual(output[2], 0.0)
        self.assertAlmostEqual(output[3], 0.0)

    def test_atr_vwap_and_volume_ratio_are_computed(self) -> None:
        self.assertEqual(atr(self.bars, 3)[:3], [None, None, 2.6666666666666665])
        self.assertAlmostEqual(vwap(self.bars)[-1], 106.66666666666667)
        self.assertEqual(volume_ratio(self.bars, 3)[2], 1.5)


if __name__ == "__main__":
    unittest.main()
