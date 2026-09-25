import logging
from typing import Final

from dishka import AsyncContainer
from dishka_faststream import setup_dishka
from faststream.rabbit import RabbitBroker

from goldy.infrastructure.task_manager.consumers import order_events, site_events

logger: Final[logging.Logger] = logging.getLogger(__name__)


def setup_notification_consumers(
    broker: RabbitBroker,
    container: AsyncContainer,
) -> None:
    """Attaches the order-event subscribers to the worker's FastStream broker.

    Two routers: the notifications, and the site handover (ADR-0004), each
    with queues of their own so one kind of outage never holds up the other.

    Two things, in this order: the dishka middleware, which opens a request
    scope per message so a subscriber can ask for ``Sender`` the way a
    Telegram handler does; then the router the subscribers are declared on.
    Called after the container is built and before the broker is started — a
    subscriber registered after ``start`` is never consumed from.

    Lives in bootstrap rather than in the entry point for the reason
    ``seed_admins`` does — ``setup`` is one of the few packages allowed to
    reach into ``application`` and ``infrastructure``, and the entry point
    stays an orchestration script.
    """
    setup_dishka(container, broker=broker)
    broker.include_router(order_events)
    broker.include_router(site_events)
    logger.debug("notifications: consumers attached to the event broker")
