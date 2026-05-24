from __future__ import annotations

import unittest

from qts.core import DataError
from qts.domain import BrokerEventType, OrderStatus
from qts.integrations.alpaca import (
    AlpacaBrokerEventSource,
    InMemoryAlpacaBrokerEventClient,
    alpaca_trade_update_to_broker_events,
)


NOW_TEXT = "2026-01-05T14:30:00Z"


def make_alpaca_order(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "alpaca-order-1",
        "client_order_id": "coid-1",
        "symbol": "SPY",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "qty": "10",
        "filled_qty": "0",
        "filled_avg_price": None,
        "status": "new",
        "created_at": NOW_TEXT,
        "submitted_at": NOW_TEXT,
        "updated_at": NOW_TEXT,
    }
    payload.update(overrides)
    return payload


class AlpacaBrokerEventTests(unittest.TestCase):
    def test_trade_update_maps_order_and_incremental_fill_events(self) -> None:
        state: dict[str, float] = {}

        first = alpaca_trade_update_to_broker_events(
            {
                "stream": "trade_updates",
                "data": {
                    "event": "partial_fill",
                    "timestamp": "2026-01-05T14:31:00Z",
                    "order": make_alpaca_order(
                        status="partially_filled",
                        filled_qty="4",
                        filled_avg_price="101",
                        updated_at="2026-01-05T14:31:00Z",
                        filled_at="2026-01-05T14:31:00Z",
                    ),
                },
            },
            filled_quantities_by_order_id=state,
        )
        duplicate = alpaca_trade_update_to_broker_events(
            {
                "data": {
                    "event": "partial_fill",
                    "order": make_alpaca_order(
                        status="partially_filled",
                        filled_qty="4",
                        filled_avg_price="101",
                        updated_at="2026-01-05T14:31:00Z",
                    ),
                }
            },
            filled_quantities_by_order_id=state,
        )

        self.assertEqual([event.event_type for event in first], [BrokerEventType.ORDER_UPDATE, BrokerEventType.FILL])
        self.assertEqual(first[0].order.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(first[1].fill.quantity, 4)
        self.assertEqual(first[1].fill.source, "alpaca_trade_updates")
        self.assertEqual([event.event_type for event in duplicate], [BrokerEventType.ORDER_UPDATE])

    def test_in_memory_source_connects_and_flattens_message_batches(self) -> None:
        client = InMemoryAlpacaBrokerEventClient(
            [
                [
                    {
                        "data": {
                            "event": "new",
                            "order": make_alpaca_order(),
                        }
                    },
                    {
                        "data": {
                            "event": "fill",
                            "order": make_alpaca_order(
                                status="filled",
                                filled_qty="10",
                                filled_avg_price="102",
                                updated_at="2026-01-05T14:32:00Z",
                                filled_at="2026-01-05T14:32:00Z",
                            ),
                        }
                    },
                ]
            ]
        )
        source = AlpacaBrokerEventSource(client)

        events = list(source.iter_events())
        source.close()

        self.assertTrue(client.subscriptions)
        self.assertTrue(client.closed)
        self.assertEqual(
            [event.event_type for event in events],
            [
                BrokerEventType.ORDER_UPDATE,
                BrokerEventType.ORDER_UPDATE,
                BrokerEventType.FILL,
            ],
        )
        self.assertEqual(events[-1].fill.quantity, 10)

    def test_error_payload_fails_closed(self) -> None:
        with self.assertRaisesRegex(DataError, "error payload"):
            alpaca_trade_update_to_broker_events({"event": "error", "message": "stream failed"})


if __name__ == "__main__":
    unittest.main()
