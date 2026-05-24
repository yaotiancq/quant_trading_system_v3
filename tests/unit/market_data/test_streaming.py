from __future__ import annotations

import unittest

from qts.core import ConfigurationError, DataError, load_runtime_config
from qts.domain import Bar, Quote
from qts.market_data import (
    AlpacaStreamEventSource,
    InMemoryAlpacaStreamClient,
    alpaca_stream_event_source_from_config,
    alpaca_stream_message_to_event,
)


class AlpacaStreamingTests(unittest.TestCase):
    def test_maps_alpaca_bar_payload_to_domain_bar(self) -> None:
        event = alpaca_stream_message_to_event(
            {
                "T": "b",
                "S": "SPY",
                "t": "2026-01-05T14:30:00Z",
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100.5,
                "v": 1000,
                "n": 12,
                "vw": 100.2,
            }
        )

        self.assertIsInstance(event, Bar)
        assert isinstance(event, Bar)
        self.assertEqual(event.symbol, "SPY")
        self.assertEqual(event.close, 100.5)
        self.assertEqual(event.trade_count, 12)
        self.assertEqual(event.source, "alpaca_stream")

    def test_maps_alpaca_quote_payload_to_domain_quote(self) -> None:
        event = alpaca_stream_message_to_event(
            {
                "T": "q",
                "S": "SPY",
                "t": "2026-01-05T14:30:00Z",
                "bp": 100.1,
                "bs": 2,
                "ap": 100.2,
                "as": 3,
            }
        )

        self.assertIsInstance(event, Quote)
        assert isinstance(event, Quote)
        self.assertEqual(event.bid_price, 100.1)
        self.assertEqual(event.ask_size, 3)

    def test_control_messages_are_ignored_and_error_messages_fail_closed(self) -> None:
        self.assertIsNone(alpaca_stream_message_to_event({"T": "success", "msg": "connected"}))
        with self.assertRaises(DataError):
            alpaca_stream_message_to_event({"T": "error", "msg": "bad auth"})

    def test_event_source_subscribes_filters_and_closes_client(self) -> None:
        client = InMemoryAlpacaStreamClient(
            [
                [
                    {"T": "subscription", "bars": ["SPY"]},
                    {
                        "T": "q",
                        "S": "SPY",
                        "t": "2026-01-05T14:30:00Z",
                        "bp": 100.1,
                        "ap": 100.2,
                    },
                    {
                        "T": "b",
                        "S": "AAPL",
                        "t": "2026-01-05T14:30:00Z",
                        "o": 100,
                        "h": 101,
                        "l": 99,
                        "c": 100.5,
                        "v": 1000,
                    },
                    {
                        "T": "b",
                        "S": "SPY",
                        "t": "2026-01-05T14:30:00Z",
                        "o": 100,
                        "h": 101,
                        "l": 99,
                        "c": 100.5,
                        "v": 1000,
                    },
                ]
            ]
        )
        source = AlpacaStreamEventSource(
            client,
            symbols=["SPY"],
            event_types=["bars"],
            feed="sip",
        )

        events = list(source.iter_events())
        source.close()

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], Bar)
        self.assertEqual(client.subscriptions[0]["symbols"], ["SPY"])
        self.assertEqual(client.subscriptions[0]["event_types"], ["bars"])
        self.assertTrue(client.closed)
        self.assertTrue(source.closed)

    def test_config_factory_uses_mock_messages(self) -> None:
        config = load_runtime_config("configs/paper_alpaca_stream_mock.yaml", env_path=None)

        source = alpaca_stream_event_source_from_config(config)
        events = list(source.iter_events())
        source.close()

        self.assertEqual(len(events), 3)
        self.assertIsInstance(events[0], Quote)
        self.assertIsInstance(events[1], Bar)

    def test_config_factory_requires_mock_messages_or_injected_client(self) -> None:
        config = load_runtime_config(
            "configs/paper_alpaca.yaml",
            env_path=None,
            overrides={"market_data": {"provider": "alpaca_stream"}},
        )

        with self.assertRaisesRegex(ConfigurationError, "mock_messages"):
            alpaca_stream_event_source_from_config(config)


if __name__ == "__main__":
    unittest.main()
