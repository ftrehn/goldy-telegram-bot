import logging
from typing import Final, override
from uuid import UUID

from goldy.application.commands.site.apply_site_order_status.command import (
    ApplySiteOrderStatusCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.ports.site import OrderHandoverDao, SiteOrderState
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus

logger: Final[logging.Logger] = logging.getLogger(__name__)


class ApplySiteOrderStatusHandler(CommandHandler[ApplySiteOrderStatusCommand, bool]):
    """Moves a handed-over order forward to where the site says it is.

    Once the site has an order, the shop works it there, and the site is the
    one that knows its status (ADR-0004). This only ever moves an order
    forward, through the aggregate's own transitions — which is what makes
    each move announce itself to the customer the ordinary way, through
    ``OrderStatusChanged``. A status the order is already past, or cannot
    reach, is left alone: a manager in the bot may have got there first, and
    a feed delivered twice must change nothing the second time.

    The site has no "shipped". ``completed`` goes straight from confirmed to
    completed, which the lifecycle allows for exactly this reason.
    """

    def __init__(
        self,
        order_handover_dao: OrderHandoverDao,
        order_command_gateway: OrderCommandGateway,
    ) -> None:
        self._order_handover_dao: Final[OrderHandoverDao] = order_handover_dao
        self._order_command_gateway: Final[OrderCommandGateway] = order_command_gateway

    @override
    async def handle(self, command: ApplySiteOrderStatusCommand) -> bool:
        status = command.status

        if not await self._order_handover_dao.record_site_status(status):
            return False

        order = await self._order_command_gateway.by_id(OrderId(UUID(status.external_id)))

        if order is None:
            return False

        moved = _follow(order, status.state)

        if moved:
            logger.info(
                "site feed: order %s is now %s (site: %s)",
                order.number,
                order.status.value,
                status.status_name,
            )

        return moved


def _follow(order: Order, state: SiteOrderState) -> bool:
    """Applies the moves that take the order to ``state``; true if any did."""
    if order.is_terminal:
        return False

    match state:
        case SiteOrderState.CONFIRMED if order.status is OrderStatus.NEW:
            order.confirm()
            return True
        case SiteOrderState.COMPLETED:
            if order.status is OrderStatus.NEW:
                order.confirm()
            order.complete()
            return True
        case SiteOrderState.CANCELLED:
            order.cancel(
                initiated_by=CancellationInitiator.SHOP,
                cancelled_by_user_id=None,
            )
            return True
        case _:
            return False
