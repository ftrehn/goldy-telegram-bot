import logging
from typing import Final

from dishka import AsyncContainer
from faststream.rabbit import RabbitBroker

from goldy.infrastructure.task_manager.consumers import setup_order_event_consumers

logger: Final[logging.Logger] = logging.getLogger(__name__)


def setup_notification_consumers(
    broker: RabbitBroker,
    container: AsyncContainer,
) -> None:
    """Attaches the order-event subscribers to the worker's FastStream broker.

    Called after the container is built and before the broker is started: a
    subscriber registered after ``start`` is never consumed from, and the
    consumers need the container to open a request scope per message.

    Lives in bootstrap rather than in the entry point for the reason
    ``seed_admins`` does — ``setup`` is one of the few packages allowed to
    reach into ``application`` and ``infrastructure``, and the entry point
    stays an orchestration script.
    """
    setup_order_event_consumers(broker, container)
    logger.debug("notifications: consumers attached to the event broker")
