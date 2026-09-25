import logging
from typing import Final, override

from goldy.application.commands.site.schedule_order_handover.command import (
    ScheduleOrderHandoverCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.site import OrderHandoverDao
from goldy.domain.orders.values.order_id import OrderId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class ScheduleOrderHandoverHandler(CommandHandler[ScheduleOrderHandoverCommand, bool]):
    """Puts the order in the handover queue; the scheduled handover sends it.

    Scheduling and sending are two steps on purpose. Sending from the event
    consumer would put a call to the site inside a message redelivered on
    every failure — immediately and forever while the site is down — whereas
    the queue retries on its own schedule with a growing delay.
    """

    def __init__(self, order_handover_dao: OrderHandoverDao) -> None:
        self._order_handover_dao: Final[OrderHandoverDao] = order_handover_dao

    @override
    async def handle(self, command: ScheduleOrderHandoverCommand) -> bool:
        scheduled = await self._order_handover_dao.schedule(OrderId(command.order_id))
        logger.info(
            "site handover: order %s %s",
            command.order_id,
            "queued" if scheduled else "was already queued",
        )
        return scheduled
