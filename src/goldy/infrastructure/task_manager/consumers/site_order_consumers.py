"""The subscribers that feed the site handover (ADR-0004).

Two queues of their own rather than a binding on the notification queues. The
notification consumers and the handover want the same ``OrderPlaced``, and a
topic exchange hands each queue its own copy — so the site being down never
holds up a manager hearing about a new order, and a Bot API outage never
delays an order reaching the site.

Scheduling needs no inbox claim: the handover queue is keyed by the order id,
and a redelivered event inserts nothing. The rejection notice is an ordinary
notification and claims its message like every other.
"""

import logging
from typing import Final

from dishka_faststream import FromDishka, inject
from faststream import AckPolicy
from faststream.rabbit import RabbitQueue, RabbitRouter
from faststream.rabbit.annotations import RabbitMessage

from goldy.application.commands.notifications.notify_handover_rejected.command import (
    NotifyOrderHandoverRejectedCommand,
)
from goldy.application.commands.site.schedule_order_handover.command import (
    ScheduleOrderHandoverCommand,
)
from goldy.application.common.events import OrderHandoverRejected
from goldy.application.common.mediator.sender import Sender
from goldy.domain.orders.events import OrderPlaced
from goldy.infrastructure.task_manager.consumers.order_event_consumers import (
    EVENTS,
    message_id_of,
    unparsable_bodies,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

SITE_ORDER_PLACED_QUEUE: Final[str] = "goldy.site.order_placed"
HANDOVER_REJECTED_QUEUE: Final[str] = "goldy.notifications.order_handover_rejected"

site_events: Final[RabbitRouter] = RabbitRouter(
    middlewares=(unparsable_bodies,),
    ack_policy=AckPolicy.NACK_ON_ERROR,
)


@site_events.subscriber(
    RabbitQueue(
        SITE_ORDER_PLACED_QUEUE,
        durable=True,
        routing_key=OrderPlaced.__name__,
    ),
    EVENTS,
)
@inject
async def on_order_placed_for_site(
    event: OrderPlaced,
    sender: FromDishka[Sender],
) -> None:
    scheduled = await sender.send(ScheduleOrderHandoverCommand(order_id=event.order_id))
    logger.debug("site handover: order %s scheduled=%s", event.order_number, scheduled)


@site_events.subscriber(
    RabbitQueue(
        HANDOVER_REJECTED_QUEUE,
        durable=True,
        routing_key=OrderHandoverRejected.__name__,
    ),
    EVENTS,
)
@inject
async def on_order_handover_rejected(
    event: OrderHandoverRejected,
    message: RabbitMessage,
    sender: FromDishka[Sender],
) -> None:
    outcome = await sender.send(
        NotifyOrderHandoverRejectedCommand(
            message_id=message_id_of(message, event),
            event_type=message.raw_message.routing_key or event.event_type,
            order_number=event.order_number,
            code=event.code,
        ),
    )
    logger.debug("notifications: order handover rejected -> %s", outcome)
