import logging
from typing import Final, override
from uuid import UUID

from goldy.application.commands.notifications import text_keys
from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_order_placed.command import (
    NotifyOrderPlacedCommand,
)
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.notifications import (
    InboxGateway,
    NotificationText,
)
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.order import OrderView
from goldy.application.common.views.user import UserView
from goldy.domain.orders.events import OrderPlaced
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.values.user_role import UserRole

logger: Final[logging.Logger] = logging.getLogger(__name__)

STAFF_ROLES: Final[tuple[UserRole, ...]] = (UserRole.MANAGER, UserRole.ADMIN)
"""Who is told about a new order. Customers are not, they just placed it."""


class NotifyOrderPlacedHandler(
    CommandHandler[NotifyOrderPlacedCommand, NotificationOutcome],
):
    """Puts a new order in front of the people who have to act on it.

    The order is read here rather than carried in the event, and that is the
    design rather than an extra query nobody noticed: the message a manager
    needs names the customer, their telephone number and where the parcel
    goes, and none of those may travel through a queue. ``OrderPlaced`` carries
    primitives and an id, and the id is what this reads by.

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
        claimed = await self._inbox_gateway.claim(
            command.message_id,
            OrderPlaced.__name__,
        )

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

        outcome = await self._dispatcher.dispatch_to_all(
            await self._staff(),
            _order_placed_text(order),
        )

        logger.info(
            "notifications: order %s announced to staff, sent=%d skipped=%d",
            order.number,
            outcome.delivered,
            outcome.skipped,
        )
        return outcome

    async def _staff(self) -> list[UserView]:
        """Everyone in a role that works orders, each of them once.

        Two queries and a deduplication rather than one query with a role list,
        because ``UserFilters`` narrows by a single role — and an administrator
        who is also on the managers' screen must still get one message.
        """
        found: dict[UUID, UserView] = {}

        for role in STAFF_ROLES:
            people = await self._user_query_gateway.read_all(
                Pagination(),
                SortingOrder.ASC,
                UserFilters(role=role),
            )
            found.update({person.id: person for person in people})

        return list(found.values())


def _order_placed_text(order: OrderView) -> NotificationText:
    return NotificationText(
        key=text_keys.NOTIFICATION_ORDER_PLACED,
        args={
            "number": order.number,
            "customer": _recipient_name(order),
            "phone": order.recipient_phone_number,
            "address": order.delivery_address,
            "lines": order.line_count,
            "total": _money(order.total),
        },
    )


def _recipient_name(order: OrderView) -> str:
    if order.recipient_last_name is None:
        return order.recipient_first_name

    return f"{order.recipient_first_name} {order.recipient_last_name}"


def _money(total: MoneyView) -> str:
    """The amount as the shop writes it, currency spelled out by its code.

    Formatted here and not by Fluent: the currency arrives as data, and a
    Fluent function may only take literal arguments — the same restriction the
    bot's own price formatter works around.
    """
    return f"{total.amount:.2f} {total.currency}"
