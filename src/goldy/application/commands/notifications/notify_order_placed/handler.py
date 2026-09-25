import logging
from typing import Final, override

from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.commands.notifications.staff import read_staff
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.notifications import (
    InboxGateway,
    OrderPlacedNotification,
)
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.views.user import UserView
from goldy.domain.orders.values.order_id import OrderId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotifyOrderPlacedHandler(
    CommandHandler[NotifyOrderPlacedCommand, NotificationOutcome],
):
    """Puts a new order in front of the people who have to act on it.

    The order is read here rather than carried in the event, and that is the
    design rather than an extra query nobody noticed: the message a manager
    needs names the customer, their telephone number and where the parcel
    goes, and none of those may travel through a queue. ``OrderPlaced`` carries
    primitives and an id, and the id is what this reads by.

    Who is told is ``STAFF_ROLES``, the domain's one statement of who works
    the shop. Customers are not among them — they just placed the order.

    Idempotency comes first, before any work. Delivery is at-least-once, so
    this handler is called again for messages it has already acted on, and a
    manager told twice about one order stops trusting the notifications.

    An order that no longer exists is not an error. Redelivery can outlive the
    row in the rare case it is removed, and raising here would put the message
    back on the queue to fail again on the next attempt.
    """

    def __init__(
        self,
        inbox_gateway: InboxGateway,
        user_query_gateway: UserQueryGateway,
        order_query_gateway: OrderQueryGateway,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._inbox_gateway: Final[InboxGateway] = inbox_gateway
        self._user_query_gateway: Final[UserQueryGateway] = user_query_gateway
        self._order_query_gateway: Final[OrderQueryGateway] = order_query_gateway
        self._dispatcher: Final[NotificationDispatcher] = dispatcher

    @override
    async def handle(self, command: NotifyOrderPlacedCommand) -> NotificationOutcome:
        claimed = await self._inbox_gateway.claim(command.message_id, command.event_type)

        if not claimed:
            logger.info(
                "notifications: message %s was handled before, dropping",
                command.message_id,
            )
            return NotificationOutcome.duplicate()

        order = await self._order_query_gateway.read_by_id(OrderId(command.order_id))

        if order is None:
            logger.warning(
                "notifications: order %s is gone, nobody to tell about it",
                command.order_id,
            )
            return NotificationOutcome(delivered=0, skipped=0)

        customer_name = " ".join(
            part
            for part in (order.recipient_first_name, order.recipient_last_name)
            if part is not None
        )
        outcome = await self._dispatcher.dispatch_to_all(
            await self._staff(),
            OrderPlacedNotification(
                number=order.number,
                customer_name=customer_name,
                phone_number=order.recipient_phone_number,
                address=order.delivery_address,
                line_count=order.line_count,
                total=order.total,
            ),
        )

        logger.info(
            "notifications: order %s announced to staff, sent=%d skipped=%d",
            order.number,
            outcome.delivered,
            outcome.skipped,
        )
        return outcome

    async def _staff(self) -> list[UserView]:
        return await read_staff(self._user_query_gateway)
