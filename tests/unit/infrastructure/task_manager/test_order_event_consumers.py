"""What the subscribers make of a broker message, driven in memory.

FastStream's test broker delivers a published message straight to the
subscriber without RabbitMQ, so the decisions written into the consumer module
can be exercised without Docker: the routing key becomes the command's
``event_type``, the AMQP ``message_id`` becomes its idempotency key with the
event's own id as the fallback, and a body this build cannot read is logged
and swallowed rather than raised back to the broker.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container
from dishka_faststream import setup_dishka
from faststream.rabbit import RabbitBroker, TestRabbitBroker

from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.notify_order_status.command import (
    NotifyOrderStatusChangedCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.domain.orders.events import OrderPlaced, OrderStatusChanged
from goldy.infrastructure.task_manager.consumers import order_events
from goldy.infrastructure.task_manager.consumers.order_event_consumers import EVENTS
from tests.unit.stubs.notifications import RecordingSender

EVENT_ID: Final[UUID] = UUID("aaaaaaaa-0000-0000-0000-000000000001")
MESSAGE_ID: Final[UUID] = UUID("bbbbbbbb-0000-0000-0000-000000000001")


def _placed(event_id: UUID = EVENT_ID) -> dict[str, Any]:
    """The JSON the relay publishes for ``OrderPlaced``, as a dictionary."""
    return {
        "event_id": str(event_id),
        "event_date": datetime(2026, 9, 13, tzinfo=UTC).isoformat(),
        "order_id": str(uuid4()),
        "order_number": "260913-3K7QXA",
        "customer_id": str(uuid4()),
        "price_type_id": "pt-retail",
        "total_amount": "10.00",
        "currency": "rub",
        "line_count": 1,
    }


@pytest.fixture()
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture()
async def broker(sender: RecordingSender) -> AsyncIterator[RabbitBroker]:
    """The subscribers on an in-memory broker, with ``Sender`` behind dishka."""
    provider = Provider(scope=Scope.REQUEST)
    provider.provide(lambda: sender, provides=Sender)
    rabbit = RabbitBroker()
    setup_dishka(make_async_container(provider), broker=rabbit)
    rabbit.include_router(order_events)

    async with TestRabbitBroker(rabbit) as test_broker:
        yield test_broker


async def test_a_published_event_becomes_the_command_keyed_by_the_message_id(
    broker: RabbitBroker,
    sender: RecordingSender,
) -> None:
    await broker.publish(
        _placed(),
        routing_key=OrderPlaced.__name__,
        exchange=EVENTS,
        message_id=str(MESSAGE_ID),
    )

    [command] = sender.requests
    assert isinstance(command, NotifyOrderPlacedCommand)
    assert command.message_id == MESSAGE_ID
    assert command.event_type == "OrderPlaced"


async def test_the_event_type_is_the_routing_key_the_message_arrived_under(
    broker: RabbitBroker,
    sender: RecordingSender,
) -> None:
    """Carried by the message, not guessed from a class the consumer imports."""
    await broker.publish(
        {
            **_placed(),
            "old_status": "new",
            "new_status": "shipped",
            "reason": None,
        },
        routing_key=OrderStatusChanged.__name__,
        exchange=EVENTS,
        message_id=str(MESSAGE_ID),
    )

    [command] = sender.requests
    assert isinstance(command, NotifyOrderStatusChangedCommand)
    assert command.event_type == "OrderStatusChanged"
    assert command.new_status == "shipped"


async def test_a_message_without_a_usable_id_is_keyed_off_the_event(
    broker: RabbitBroker,
    sender: RecordingSender,
) -> None:
    """A replay by hand still gets the key it would have had."""
    await broker.publish(
        _placed(),
        routing_key=OrderPlaced.__name__,
        exchange=EVENTS,
        message_id="not-a-uuid",
    )

    [command] = sender.requests
    assert command.message_id == EVENT_ID


async def test_a_body_this_build_cannot_read_is_dropped_not_retried(
    broker: RabbitBroker,
    sender: RecordingSender,
) -> None:
    """Redelivering it would fail forever in front of the messages behind it."""
    await broker.publish(
        {"garbage": True},
        routing_key=OrderPlaced.__name__,
        exchange=EVENTS,
        message_id=str(MESSAGE_ID),
    )

    assert sender.requests == []
