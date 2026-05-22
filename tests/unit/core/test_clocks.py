from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from qts.core import ClockError, RealClock, ReplayClock


UTC = timezone.utc


class ClockTests(unittest.TestCase):
    def test_real_clock_returns_timezone_aware_utc_timestamp(self) -> None:
        now = RealClock().now()

        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))

    def test_replay_clock_advances_by_step_or_explicit_timestamp(self) -> None:
        clock = ReplayClock(datetime(2026, 1, 5, 14, 30, tzinfo=UTC), step_size=timedelta(minutes=1))

        self.assertEqual(clock.advance(), datetime(2026, 1, 5, 14, 31, tzinfo=UTC))
        self.assertEqual(
            clock.advance(datetime(2026, 1, 5, 14, 35, tzinfo=UTC)),
            datetime(2026, 1, 5, 14, 35, tzinfo=UTC),
        )

    def test_replay_clock_rejects_backward_advance(self) -> None:
        clock = ReplayClock(datetime(2026, 1, 5, 14, 30, tzinfo=UTC))

        with self.assertRaises(ClockError):
            clock.advance(datetime(2026, 1, 5, 14, 29, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
