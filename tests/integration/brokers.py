"""The broker end of the outbox, without a RabbitMQ to talk to.

``TestRabbitBroker`` routes publishes in process, through the same FastStream
API the relay uses — so :class:`FastStreamOutboxPublisher` is the real one and
its two invariants stay observable: the outbox row id travels as ``message_id``,
and the body is JSON rather than text.

One thing diverges from a real topic exchange, and it matters. A real broker
silently drops a message nobody is bound to; the in-memory one raises
``SubscriberNotFound``. The publisher wraps that into ``OutboxPublishError``,
which ``RelayOutboxHandler`` catches and skips — so a missing subscriber would
show up as ``published=0`` with no hint why. The catch-all binding below exists
to make that impossible.
"""

import json
from dataclasses import dataclass
from typing import Any, Final, final

from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitMessage,
    RabbitQueue,
)

EVENTS_EXCHANGE: Final[str] = "domain_events"
"""Mirrors the private constant in the publisher.

Duplicated on purpose: the test binds to the exchange the way a consumer in
another service would, and a consumer does not get to import our constants.
"""

CAPTURE_QUEUE: Final[str] = "tests.capture"
CATCH_ALL_ROUTING_KEY: Final[str] = "#"


@final
@dataclass(frozen=True, slots=True)
class PublishedEvent:
    """One message as a consumer on the other side would receive it."""

    message_id: str | None
    routing_key: str | None
    content_type: str | None
    body: dict[str, Any]


@final
class PublishedEvents:
    """Everything the relay handed to the broker, in order.

    Cleared between tests rather than rebuilt, because the broker outlives the
    session: without that a test could pass on an event its neighbour published.
    """

    def __init__(self) -> None:
        self._events: Final[list[PublishedEvent]] = []

    def record(self, event: PublishedEvent) -> None:
        self._events.append(event)

    def all(self) -> tuple[PublishedEvent, ...]:
        return tuple(self._events)

    def routing_keys(self) -> tuple[str | None, ...]:
        return tuple(event.routing_key for event in self._events)

    def message_ids(self) -> frozenset[str | None]:
        return frozenset(event.message_id for event in self._events)

    def forget(self) -> None:
        self._events.clear()


def make_recording_event_broker() -> tuple[RabbitBroker, PublishedEvents]:
    """A FastStream broker with one binding that keeps whatever arrives."""
    broker: Final[RabbitBroker] = RabbitBroker()
    published: Final[PublishedEvents] = PublishedEvents()

    exchange: Final[RabbitExchange] = RabbitExchange(
        EVENTS_EXCHANGE,
        type=ExchangeType.TOPIC,
        durable=True,
    )

    @broker.subscriber(
        RabbitQueue(CAPTURE_QUEUE, routing_key=CATCH_ALL_ROUTING_KEY),
        exchange,
    )
    async def capture(message: RabbitMessage) -> None:  # ruff: ignore[unused-async]
        published.record(
            PublishedEvent(
                message_id=message.message_id,
                routing_key=message.raw_message.routing_key,
                content_type=message.content_type,
                body=json.loads(message.body),
            ),
        )

    return broker, published
