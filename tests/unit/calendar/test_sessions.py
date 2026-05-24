from __future__ import annotations

import unittest
from datetime import date

from qts.calendar import MarketSessionConfig, MarketSessionService
from qts.core import CalendarError, ConfigurationError


class FailingCalendar:
    def session_for_date(self, session_date, config):  # type: ignore[no-untyped-def]
        raise CalendarError("calendar unavailable")


class MarketSessionServiceTests(unittest.TestCase):
    def test_regular_session_boundaries_are_open_inclusive_close_exclusive(self) -> None:
        service = MarketSessionService()

        self.assertTrue(service.is_regular_session("2026-01-05T14:30:00Z"))
        self.assertTrue(service.is_regular_session("2026-01-05T20:59:59Z"))
        self.assertFalse(service.is_regular_session("2026-01-05T21:00:00Z"))

    def test_weekend_and_holiday_are_closed(self) -> None:
        service = MarketSessionService()

        self.assertFalse(service.is_tradable("2026-01-03T15:00:00Z"))
        self.assertFalse(service.is_tradable("2026-01-01T15:00:00Z"))

    def test_early_close_uses_exchange_close_time(self) -> None:
        service = MarketSessionService()
        session = service.session_for_date(date(2026, 11, 27))

        self.assertIsNotNone(session)
        assert session is not None
        self.assertTrue(session.early_close)
        self.assertTrue(service.is_regular_session("2026-11-27T17:59:59Z"))
        self.assertFalse(service.is_regular_session("2026-11-27T18:00:00Z"))

    def test_timezone_conversion_handles_daylight_saving_time(self) -> None:
        service = MarketSessionService()

        self.assertTrue(service.is_regular_session("2026-05-22T13:30:00Z"))
        self.assertFalse(service.is_regular_session("2026-05-22T20:00:00Z"))

    def test_regular_session_only_rejects_premarket(self) -> None:
        service = MarketSessionService()

        self.assertFalse(service.is_tradable("2026-01-05T12:00:00Z"))

    def test_extended_hours_mode_accepts_configured_extended_windows(self) -> None:
        service = MarketSessionService(
            {
                "regular_session_only": False,
                "extended_hours": {"enabled": True},
            }
        )

        self.assertTrue(service.is_tradable("2026-01-05T12:00:00Z"))
        self.assertTrue(service.is_tradable("2026-01-05T22:00:00Z"))
        self.assertFalse(service.is_tradable("2026-01-06T01:00:00Z"))

    def test_current_or_next_session_returns_future_session_after_close(self) -> None:
        service = MarketSessionService()

        session = service.current_or_next_session("2026-01-05T22:00:00Z")

        self.assertEqual(session.session_date, date(2026, 1, 6))

    def test_fail_closed_returns_false_when_provider_cannot_resolve(self) -> None:
        service = MarketSessionService(provider=FailingCalendar())

        self.assertFalse(service.is_tradable("2026-01-05T14:30:00Z"))

    def test_fail_open_raises_when_provider_cannot_resolve(self) -> None:
        service = MarketSessionService({"fail_closed": False}, provider=FailingCalendar())

        with self.assertRaises(CalendarError):
            service.is_tradable("2026-01-05T14:30:00Z")

    def test_invalid_exchange_and_timezone_fail_config_validation(self) -> None:
        with self.assertRaises(ConfigurationError):
            MarketSessionConfig.from_mapping({"exchange": "CRYPTO"})
        with self.assertRaises(ConfigurationError):
            MarketSessionConfig.from_mapping({"timezone": "No/Such_Zone"})


if __name__ == "__main__":
    unittest.main()
