"""What the outbox makes of the three order events.

Not a test of adaptix. What is pinned here is that the events an order records
are made of things the existing serialiser already knows how to write — that
the total travels as a string rather than as a ``Decimal`` ``json.dumps`` would
refuse, and that no personal data crept into a payload that ends up on a
RabbitMQ exchange with no consumer behind it.
"""

import json
from typing import Any

from goldy.application.common.ports.outbox import OutboxMessage
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.infrastructure.adapters.outbox.retort_event_serializer import (
    RetortEventSerializer,
)
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    ORDER_NUMBER,
    make_delivery_address,
    make_order,
    make_order_line,
)
from tests.unit.support import emitted_events

SERIALIZER = RetortEventSerializer()

NEW_ADDRESS = "Санкт-Петербург, Невский проспект 20, кв. 3"
CANCELLATION_REASON = "Товара не оказалось на складе"


def _messages(collection: EventsCollection) -> list[OutboxMessage]:
    return [SERIALIZER.serialize(event) for event in emitted_events(collection)]


def _payload(message: OutboxMessage) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(message.payload)
    return parsed


def test_placing_an_order_produces_a_payload_json_accepts() -> None:
    """The total is a string because JSON has no decimal and floats lose kopecks."""
    order, collection = make_order(lines=(make_order_line(quantity=3),))

    payload = _payload(_messages(collection)[0])

    assert payload["total_amount"] == str(order.total.amount)
    assert isinstance(payload["total_amount"], str)
    assert payload["currency"] == "rub"
    assert payload["line_count"] == 1
    assert payload["order_number"] == ORDER_NUMBER


def test_an_order_event_carries_no_personal_data() -> None:
    """The exchange has no consumer yet, so nothing rides along for later."""
    _, collection = make_order()

    payload = _payload(_messages(collection)[0])

    assert "delivery_address" not in payload
    assert "recipient_name" not in payload
    assert "recipient_phone" not in payload


def test_the_outbox_row_reuses_the_identity_the_event_was_stamped_with() -> None:
    """Re-serialising one fact must not turn it into two messages downstream."""
    _, collection = make_order()
    [event] = emitted_events(collection)

    message = SERIALIZER.serialize(event)

    assert message.id == event.event_id
    assert message.created_at == event.event_date
    assert message.event_type == "OrderPlaced"
    assert _payload(message)["event_id"] == str(event.event_id)


def test_every_transition_serialises_through_the_one_status_event() -> None:
    order, collection = make_order(status=OrderStatus.CONFIRMED)
    order.cancel(
        initiated_by=CancellationInitiator.MANAGER,
        reason=CancellationReason(value=CANCELLATION_REASON),
    )

    messages = _messages(collection)

    assert [message.event_type for message in messages] == [
        "OrderPlaced",
        "OrderStatusChanged",
        "OrderStatusChanged",
    ]
    assert _payload(messages[-1])["new_status"] == "cancelled"
    assert _payload(messages[-1])["reason"] == CANCELLATION_REASON


def test_a_status_event_without_a_reason_keeps_null() -> None:
    _, collection = make_order(status=OrderStatus.CONFIRMED)

    payload = _payload(_messages(collection)[-1])

    assert payload["old_status"] == "new"
    assert payload["new_status"] == "confirmed"
    assert payload["reason"] is None


def test_a_readdressed_order_reports_both_addresses() -> None:
    """The one event where an address is the fact rather than a passenger."""
    order, collection = make_order()
    order.change_delivery_address(make_delivery_address(NEW_ADDRESS))

    payload = _payload(_messages(collection)[-1])

    assert payload["old_address"] == DELIVERY_ADDRESS
    assert payload["new_address"] == NEW_ADDRESS
    assert "recipient_phone" not in payload
