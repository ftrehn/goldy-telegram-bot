import json
from typing import Any, Final, final, override

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from goldy.application.common.ports.outbox.outbox_message import OutboxMessage
from goldy.application.common.ports.outbox.outbox_publisher import OutboxPublisher
from goldy.infrastructure.errors import OutboxPublishError

_EVENTS_EXCHANGE: Final[str] = "domain_events"


@final
class FastStreamOutboxPublisher(OutboxPublisher):
    """Publishes outbox messages to RabbitMQ via FastStream.

    Two important invariants are enforced on every publish:

    ``message_id`` is set to ``str(message.id)`` — the outbox record UUID.
    This value is stable across retries (the outbox row never changes its PK),
    so consumers running InboxMiddleware can use it as an idempotency key.

    ``message.payload`` is a JSON string produced by RetortEventSerializer.
    It is parsed back to a dict before handing it to FastStream so that
    FastStream sets ``content_type: application/json`` and serialises the
    dict correctly.  Publishing a raw ``str`` would cause FastStream to set
    ``content_type: text/plain``, which breaks consumers that expect a
    structured JSON body.
    """

    def __init__(self, broker: RabbitBroker) -> None:
        self._broker: Final[RabbitBroker] = broker
        self._exchange: Final[RabbitExchange] = RabbitExchange(
            _EVENTS_EXCHANGE,
            type=ExchangeType.TOPIC,
            durable=True,
        )
        self._exchange_declared: bool = False

    @override
    async def publish(self, message: OutboxMessage) -> None:
        try:
            if not self._exchange_declared:
                await self._broker.declare_exchange(self._exchange)
                self._exchange_declared = True

            body: dict[str, Any] = json.loads(message.payload)
            await self._broker.publish(
                message=body,
                routing_key=message.event_type,
                exchange=self._exchange,
                message_id=str(message.id),
            )
        except Exception as exc:
            raise OutboxPublishError(str(exc)) from exc
