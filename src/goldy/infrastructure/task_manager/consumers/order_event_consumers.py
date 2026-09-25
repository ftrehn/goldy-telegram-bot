"""The RabbitMQ subscribers that turn order events into notification commands.

Ordinary FastStream subscribers on a router, the way the framework means them
to be written: the body is parsed into the event by its annotation, the
container is reached through ``FromDishka`` the way the Telegram handlers reach
it, and the request scope is opened per message by the dishka middleware the
worker installs. There is no class holding a container and no hand-written
parser — FastStream already does both.

Three queues rather than one with three bindings. A queue is where a message
waits, and a status change that cannot be delivered must not hold up the new
orders behind it — separate queues put the blast radius of a poisoned message
inside the kind of message that poisoned it.

Delivery is at-least-once from end to end: the relay marks an outbox row
processed only after the transport accepted it, so a crash between the two
re-publishes it. Every command below therefore carries the AMQP ``message_id``,
which is the outbox row's primary key and does not change between retries, and
the handlers refuse a key they have already seen. The event type travels beside
it as the routing key the message arrived under — the name the relay published
it by — so the inbox records what each claim was for.

What is *not* retried matters as much. ``NACK_ON_ERROR`` puts a failed message
back, which is right for the database, the Bot API and the broker being down —
and wrong for a body that does not parse, which would fail forever in front of
the messages behind it. The exception middleware acknowledges those after
logging them, and nothing else.
"""

import logging
from typing import Final
from uuid import UUID

from dishka_faststream import FromDishka, inject
from faststream import AckPolicy, ExceptionMiddleware
from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue, RabbitRouter
from faststream.rabbit.annotations import RabbitMessage

from goldy.application.commands.notifications.notify_order_address.command import (
    NotifyDeliveryAddressChangedCommand,
)
from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.notify_order_status.command import (
    NotifyOrderStatusChangedCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.domain.common.event import Event
from goldy.domain.orders.events import (
    OrderDeliveryAddressChanged,
    OrderPlaced,
    OrderStatusChanged,
)
from goldy.infrastructure.adapters.outbox.faststream_outbox_publisher import (
    EVENTS_EXCHANGE,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

ORDER_PLACED_QUEUE: Final[str] = "goldy.notifications.order_placed"
ORDER_STATUS_QUEUE: Final[str] = "goldy.notifications.order_status_changed"
ORDER_ADDRESS_QUEUE: Final[str] = "goldy.notifications.order_address_changed"

EVENTS: Final[RabbitExchange] = RabbitExchange(
    EVENTS_EXCHANGE,
    type=ExchangeType.TOPIC,
    durable=True,
)
"""The exchange the relay publishes to, declared from the same name it reads."""

unparsable_bodies: Final[ExceptionMiddleware] = ExceptionMiddleware()
"""Acknowledges a message whose body this build cannot read, after logging it.

A ``ValueError`` here is the parser refusing the body — FastStream's validation
errors are ``ValueError``s — and redelivering it produces the same refusal
forever in front of the messages behind it.
"""


@unparsable_bodies.add_handler(ValueError)
def log_unparsable_body(exc: ValueError) -> None:
    logger.error("notifications: cannot read an order event", exc_info=exc)


order_events: Final[RabbitRouter] = RabbitRouter(
    middlewares=(unparsable_bodies,),
    ack_policy=AckPolicy.NACK_ON_ERROR,
)


@order_events.subscriber(
    RabbitQueue(ORDER_PLACED_QUEUE, durable=True, routing_key=OrderPlaced.__name__),
    EVENTS,
)
@inject
async def on_order_placed(
    event: OrderPlaced,
    message: RabbitMessage,
    sender: FromDishka[Sender],
) -> None:
    outcome = await sender.send(
        NotifyOrderPlacedCommand(
            message_id=message_id_of(message, event),
            event_type=message.raw_message.routing_key or event.event_type,
            order_id=event.order_id,
        ),
    )
    logger.debug("notifications: order placed -> %s", outcome)


@order_events.subscriber(
    RabbitQueue(
        ORDER_STATUS_QUEUE,
        durable=True,
        routing_key=OrderStatusChanged.__name__,
    ),
    EVENTS,
)
@inject
async def on_order_status_changed(
    event: OrderStatusChanged,
    message: RabbitMessage,
    sender: FromDishka[Sender],
) -> None:
    outcome = await sender.send(
        NotifyOrderStatusChangedCommand(
            message_id=message_id_of(message, event),
            event_type=message.raw_message.routing_key or event.event_type,
            order_number=event.order_number,
            customer_id=event.customer_id,
            new_status=event.new_status,
            reason=event.reason,
        ),
    )
    logger.debug("notifications: order status changed -> %s", outcome)


@order_events.subscriber(
    RabbitQueue(
        ORDER_ADDRESS_QUEUE,
        durable=True,
        routing_key=OrderDeliveryAddressChanged.__name__,
    ),
    EVENTS,
)
@inject
async def on_order_address_changed(
    event: OrderDeliveryAddressChanged,
    message: RabbitMessage,
    sender: FromDishka[Sender],
) -> None:
    outcome = await sender.send(
        NotifyDeliveryAddressChangedCommand(
            message_id=message_id_of(message, event),
            event_type=message.raw_message.routing_key or event.event_type,
            order_number=event.order_number,
            customer_id=event.customer_id,
            old_address=event.old_address,
            new_address=event.new_address,
        ),
    )
    logger.debug("notifications: order address changed -> %s", outcome)


def message_id_of(message: RabbitMessage, event: Event) -> UUID:
    """The outbox row id this delivery is a copy of.

    Read from the AMQP ``message_id`` the publisher sets, which survives every
    redelivery. The event's own identity is the same value — the outbox row
    reuses it rather than minting one — so a message that arrives without the
    header, replayed by hand or published by an older build, still gets the key
    it would have had.
    """
    try:
        return UUID(str(message.message_id))
    except ValueError:
        logger.warning(
            "notifications: message_id %r is unusable, keying off the event %s",
            message.message_id,
            event.event_type,
        )
        return event.event_id
