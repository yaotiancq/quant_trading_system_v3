from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.core import ConfigurationError
from qts.domain import Bar, BarTimeframe, Quote
from qts.market_data import InMemoryRuntimeDataPortal


NOW = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def make_bar(
    symbol: str = "SPY",
    *,
    minutes: int = 0,
    close: float = 100,
) -> Bar:
    timestamp = NOW + timedelta(minutes=minutes)
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        timeframe=BarTimeframe.MINUTE,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
    )


def make_quote(symbol: str = "SPY", *, minutes: int = 0) -> Quote:
    return Quote(
        symbol=symbol,
        timestamp=NOW + timedelta(minutes=minutes),
        bid_price=100,
        ask_price=100.2,
    )


class InMemoryRuntimeDataPortalTests(unittest.TestCase):
    def test_advancing_bar_stores_current_bar(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        bar = make_bar()

        portal.advance(bar)

        self.assertEqual(portal.get_current_bar("SPY"), bar)
        self.assertEqual(portal.get_bars("SPY"), [bar])

    def test_multiple_bars_preserve_chronological_retrieval(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        bars = [make_bar(minutes=minute, close=100 + minute) for minute in range(3)]

        for bar in bars:
            portal.advance(bar)

        self.assertEqual(portal.get_bars("SPY"), bars)

    def test_lookback_retrieval_returns_latest_bars(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        bars = [make_bar(minutes=minute, close=100 + minute) for minute in range(4)]
        for bar in bars:
            portal.advance(bar)

        self.assertEqual(portal.get_bars("SPY", lookback=2), bars[-2:])

    def test_advancing_quote_stores_current_quote(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        quote = make_quote()

        portal.advance(quote)

        self.assertEqual(portal.get_quote("SPY"), quote)

    def test_quote_does_not_overwrite_current_bar(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        bar = make_bar()
        quote = make_quote(minutes=1)

        portal.advance(bar)
        portal.advance(quote)

        self.assertEqual(portal.get_current_bar("SPY"), bar)
        self.assertEqual(portal.get_quote("SPY"), quote)

    def test_bar_retention_limit_is_enforced_per_symbol(self) -> None:
        portal = InMemoryRuntimeDataPortal(max_bars_per_symbol=2)
        spy_bars = [make_bar("SPY", minutes=minute, close=100 + minute) for minute in range(3)]
        aapl_bar = make_bar("AAPL", minutes=1, close=200)
        for bar in [spy_bars[0], aapl_bar, spy_bars[1], spy_bars[2]]:
            portal.advance(bar)

        self.assertEqual(portal.get_bars("SPY"), spy_bars[-2:])
        self.assertEqual(portal.get_bars("AAPL"), [aapl_bar])

    def test_multiple_symbols_are_stored_independently(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        spy_bar = make_bar("SPY")
        aapl_bar = make_bar("AAPL", close=200)

        portal.advance(spy_bar)
        portal.advance(aapl_bar)

        self.assertEqual(portal.get_bars("SPY"), [spy_bar])
        self.assertEqual(portal.get_bars("AAPL"), [aapl_bar])
        self.assertEqual(portal.get_current_bar("spy"), spy_bar)
        self.assertEqual(portal.get_current_bar("aapl"), aapl_bar)

    def test_symbols_are_normalized_consistently(self) -> None:
        portal = InMemoryRuntimeDataPortal()
        bar = make_bar(" spy ")
        quote = make_quote(" spy ")

        portal.advance(bar)
        portal.advance(quote)

        self.assertEqual(portal.get_bars("spy"), [bar])
        self.assertEqual(portal.get_current_bar(" SPY "), bar)
        self.assertEqual(portal.get_quote("spy"), quote)

    def test_invalid_retention_limit_fails_fast(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "max_bars_per_symbol"):
            InMemoryRuntimeDataPortal(max_bars_per_symbol=0)


if __name__ == "__main__":
    unittest.main()
