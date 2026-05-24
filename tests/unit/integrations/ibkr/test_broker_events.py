from __future__ import annotations

import unittest

from qts.core import DataError
from qts.domain import BrokerEventType, OrderStatus
from qts.integrations.ibkr import (
    IBKRBrokerEventSource,
    InMemoryIBKRBrokerEventClient,
    ibkr_order_update_to_broker_events,
)


NOW_TEXT = "2026-01-05T14:30:00Z"


def make_ibkr_order(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "order_id": "ibkr-order-1",
        "cOID": "coid-1",
        "ticker": "SPY",
        "side": "BUY",
        "orderType": "MKT",
        "quantity": 10,
        "filledQuantity": 0,
        "avgPrice": None,
        "order_status": "Submitted",
        "created_at": NOW_TEXT,
        "updated_at": NOW_TEXT,
        "conid": 756733,
    }
    payload.update(overrides)
    return payload


class IBKRBrokerEventTests(unittest.TestCase):
    def test_order_update_maps_order_and_incremental_fill_events(self) -> None:
        state: dict[str, float] = {}

        first = ibkr_order_update_to_broker_events(
            {
                "topic": "orderStatus",
                "data": make_ibkr_order(
                    order_status="Filled",
                    filledQuantity=10,
                    avgPrice=101,
                    updated_at="2026-01-05T14:31:00Z",
                ),
            },
            account_id="DU123456",
            filled_quantities_by_order_id=state,
        )
        duplicate = ibkr_order_update_to_broker_events(
            make_ibkr_order(
                order_status="Filled",
                filledQuantity=10,
                avgPrice=101,
                updated_at="2026-01-05T14:31:00Z",
            ),
            account_id="DU123456",
            filled_quantities_by_order_id=state,
        )

        self.assertEqual([event.event_type for event in first], [BrokerEventType.ORDER_UPDATE, BrokerEventType.FILL])
        self.assertEqual(first[0].order.status, OrderStatus.FILLED)
        self.assertEqual(first[0].order.metadata["account_id"], "DU123456")
        self.assertEqual(first[1].fill.quantity, 10)
        self.assertEqual(first[1].fill.source, "ibkr_order_updates")
        self.assertEqual([event.event_type for event in duplicate], [BrokerEventType.ORDER_UPDATE])

    def test_in_memory_source_connects_and_flattens_order_batches(self) -> None:
        client = InMemoryIBKRBrokerEventClient(
            [
                {
                    "orders": [
                        make_ibkr_order(),
                        make_ibkr_order(
                            order_status="Filled",
                            filledQuantity=5,
                            avgPrice=100,
                            updated_at="2026-01-05T14:31:00Z",
                        ),
                    ]
                }
            ]
        )
        source = IBKRBrokerEventSource(client, account_id="DU123456")

        events = list(source.iter_events())
        source.close()

        self.assertEqual(client.subscriptions, [{"account_id": "DU123456"}])
        self.assertTrue(client.closed)
        self.assertEqual(
            [event.event_type for event in events],
            [
                BrokerEventType.ORDER_UPDATE,
                BrokerEventType.ORDER_UPDATE,
                BrokerEventType.FILL,
            ],
        )
        self.assertEqual(events[-1].fill.quantity, 5)

    def test_error_payload_fails_closed(self) -> None:
        with self.assertRaisesRegex(DataError, "error payload"):
            ibkr_order_update_to_broker_events({"type": "error", "message": "stream failed"})


if __name__ == "__main__":
    unittest.main()
