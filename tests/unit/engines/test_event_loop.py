from __future__ import annotations

import unittest
from datetime import datetime, timezone

from qts.calendar import MarketSessionService
from qts.core import DataError, ReplayClock
from qts.domain import Bar, BarTimeframe
from qts.engines import InMemoryMarketEventSource, RuntimeEventLoop


def make_bar(timestamp: str) -> Bar:
    return Bar(
        symbol="SPY",
        timestamp=timestamp,
        timeframe=BarTimeframe.MINUTE,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1000,
    )


class RuntimeEventLoopTests(unittest.TestCase):
    def test_fake_source_coerces_mapping_events_and_dispatches_until_limit(self) -> None:
        source = InMemoryMarketEventSource(
            [
                {
                    "type": "bar",
                    "symbol": "SPY",
                    "timestamp": "2026-01-05T14:30:00Z",
                    "timeframe": "MINUTE",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100,
                    "volume": 1000,
                },
                make_bar("2026-01-05T14:31:00Z"),
            ]
        )
        seen: list[Bar] = []

        result = RuntimeEventLoop(source, seen.append).run(max_events=1)

        self.assertEqual(result.processed_count, 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].symbol, "SPY")
        self.assertTrue(source.closed)

    def test_duplicate_events_are_skipped(self) -> None:
        bar = make_bar("2026-01-05T14:30:00Z")
        source = InMemoryMarketEventSource([bar, bar])
        seen: list[Bar] = []

        result = RuntimeEventLoop(source, seen.append).run()

        self.assertEqual(result.processed_count, 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(len(seen), 1)
        self.assertTrue(source.closed)

    def test_out_of_order_events_fail_closed(self) -> None:
        source = InMemoryMarketEventSource(
            [
                make_bar("2026-01-05T14:31:00Z"),
                make_bar("2026-01-05T14:30:00Z"),
            ]
        )

        with self.assertRaises(DataError):
            RuntimeEventLoop(source, lambda event: None).run()

        self.assertTrue(source.closed)

    def test_stale_events_fail_when_freshness_gate_is_enabled(self) -> None:
        source = InMemoryMarketEventSource([make_bar("2026-01-05T14:30:00Z")])
        clock = ReplayClock(datetime(2026, 1, 5, 14, 35, tzinfo=timezone.utc))

        with self.assertRaises(DataError):
            RuntimeEventLoop(
                source,
                lambda event: None,
                clock=clock,
                max_staleness_seconds=60,
            ).run()

        self.assertTrue(source.closed)

    def test_session_filter_skips_events_outside_configured_session(self) -> None:
        source = InMemoryMarketEventSource(
            [
                make_bar("2026-01-05T21:00:00Z"),
                make_bar("2026-01-05T14:30:00Z"),
            ]
        )
        seen: list[Bar] = []

        result = RuntimeEventLoop(
            source,
            seen.append,
            session_service=MarketSessionService({"exchange": "XNYS"}),
        ).run(max_events=1)

        self.assertEqual(result.processed_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(seen[0].timestamp, datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc))
        self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
