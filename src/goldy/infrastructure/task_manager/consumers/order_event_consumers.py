"""The first RabbitMQ consumers in the project, and what they are careful about.

Domain events reach a topic exchange through the outbox relay. Until now
nothing bound to it: the events were published and dropped, and a customer
found out their order had shipped by opening ``/orders``. These three
subscribers turn each published fact into a notification command.

Three queues rather than one with three bindings. A queue is where a message
waits, and a status change that cannot be delivered must not hold up the new
orders behind it — separate queues put the blast radius of a poisoned message
inside the kind of message that poisoned it.

Delivery is at-least-once from end to end: the relay marks an outbox row
processed only after the transport accepted it, so a crash between the two
re-publishes it. Everything below therefore keys off ``message_id``, which is
the outbox row's primary key and does not change between retries, and the
handlers refuse a key they have already seen.

What is *not* retried matters as much. A payload that does not parse is logged
and acknowledged, because redelivering it produces the same failure forever;
only failures that could plausibly succeed next time — the database, the Bot
API, the broker — are allowed to raise and send the message back.
"""

import json
import logging
from collections.abc import Callable, Coroutine
from typing import Final, final
from uuid import UUID

from adaptix import Retort
from adaptix.load_error import LoadError
from dishka import AsyncContainer, Scope
from faststream import AckPolicy
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue
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
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import BaseRequest
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

_retort: Final[Retort] = Retort()
"""Plain, on purpose.

The serialiser needs dumpers for ``UUID`` and ``datetime`` because
``json.dumps`` knows neither; loading back needs no recipe at all, because
adaptix reads both from the annotations of the event that is being loaded.
"""

type _Consumer = Callable[[RabbitMessage], Coroutine[None, None, None]]


@final
class OrderEventConsumers:
    """Turns published order events into notification commands.

    Holds the application-wide container and opens a request scope per message,
    the way ``seed_admins`` does for a startup command: there is no update to
    hang a scope off, and the command still needs a session and a transaction
    like any other.

    Dispatches through ``Sender`` rather than calling a handler, because the
    inbox claim and whatever the notification caused have to commit together —
    and the transaction that makes that true is opened by the pipeline.
    """

    def __init__(self, container: AsyncContainer) -> None:
        self._container: Final[AsyncContainer] = container

    async def on_order_placed(self, message: RabbitMessage) -> None:
        event = _read(message, OrderPlaced)

        if event is None:
            return

        await self._send(
            NotifyOrderPlacedCommand(
                message_id=_idempotency_key(message, event),
                order_id=event.order_id,
            ),
        )

    async def on_order_status_changed(self, message: RabbitMessage) -> None:
        event = _read(message, OrderStatusChanged)

        if event is None:
            return

        await self._send(
            NotifyOrderStatusChangedCommand(
                message_id=_idempotency_key(message, event),
                order_number=event.order_number,
                customer_id=event.customer_id,
                new_status=event.new_status,
                reason=event.reason,
            ),
        )

    async def on_order_address_changed(self, message: RabbitMessage) -> None:
        event = _read(message, OrderDeliveryAddressChanged)

        if event is None:
            return

        await self._send(
            NotifyDeliveryAddressChangedCommand(
                message_id=_idempotency_key(message, event),
                order_number=event.order_number,
                customer_id=event.customer_id,
                old_address=event.old_address,
                new_address=event.new_address,
            ),
        )

    async def _send(self, command: BaseRequest[NotificationOutcome]) -> None:
        async with self._container(scope=Scope.REQUEST) as request_container:
            sender = await request_container.get(Sender)
            outcome = await sender.send(command)

        logger.debug(
            "notifications: %s -> sent=%d skipped=%d duplicate=%s",
            type(command).__name__,
            outcome.delivered,
            outcome.skipped,
            outcome.already_handled,
        )


def setup_order_event_consumers(
    broker: RabbitBroker,
    container: AsyncContainer,
) -> None:
    """Binds one durable queue per order event to the domain exchange.

    The routing key is the event's class name, which is what the relay
    publishes under, so the binding is written from the same string the
    publisher reads off ``OutboxMessage.event_type``.

    ``NACK_ON_ERROR`` puts a failed message back rather than discarding it.
    That is safe only because the handlers do not raise on the failures that
    would repeat — an unknown user, a blocked account, a deleted order are all
    answers, not exceptions — so anything that does raise is worth another go.
    """
    consumers = OrderEventConsumers(container)
    exchange = RabbitExchange(EVENTS_EXCHANGE, type=ExchangeType.TOPIC, durable=True)

    bindings: tuple[tuple[str, str, _Consumer], ...] = (
        (ORDER_PLACED_QUEUE, OrderPlaced.__name__, consumers.on_order_placed),
        (
            ORDER_STATUS_QUEUE,
            OrderStatusChanged.__name__,
            consumers.on_order_status_changed,
        ),
        (
            ORDER_ADDRESS_QUEUE,
            OrderDeliveryAddressChanged.__name__,
            consumers.on_order_address_changed,
        ),
    )

    for queue_name, routing_key, consumer in bindings:
        broker.subscriber(
            RabbitQueue(queue_name, durable=True, routing_key=routing_key),
            exchange,
            ack_policy=AckPolicy.NACK_ON_ERROR,
        )(consumer)

    logger.info("notifications: subscribed to %d order event(s)", len(bindings))


def _read[EventT: Event](
    message: RabbitMessage, event_type: type[EventT]
) -> EventT | None:
    """The published event, or nothing when the body cannot be understood.

    Nothing rather than an exception. A body this build cannot parse will not
    parse on the next delivery either, and letting it raise would hand the
    broker a message that fails forever in front of the ones behind it.
    """
    try:
        return _retort.load(json.loads(message.body), event_type)
    except ValueError, TypeError, LoadError:
        logger.exception(
            "notifications: cannot read %s from message %s",
            event_type.__name__,
            message.message_id,
        )
        return None


def _idempotency_key(message: RabbitMessage, event: Event) -> UUID:
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
