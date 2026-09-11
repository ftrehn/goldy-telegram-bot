import logging
from typing import Final, override

from goldy.application.commands.notifications import text_keys
from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_order_address.command import (
    NotifyDeliveryAddressChangedCommand,
)
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.notifications import (
    InboxGateway,
    NotificationText,
)
from goldy.application.common.ports.users import UserQueryGateway
from goldy.domain.orders.events import OrderDeliveryAddressChanged
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotifyDeliveryAddressChangedHandler(
    CommandHandler[NotifyDeliveryAddressChangedCommand, NotificationOutcome],
):
    """Confirms to the buyer that their correction took effect.

    The whole reason the address may be edited after the order is placed is
    that getting it wrong is the most painful mistake to make; a correction
    that is silently accepted leaves the person wondering whether it was, and
    they ring the shop to ask.

    Both addresses go in the message. The aggregate keeps only the new one, so
    "was → now" exists nowhere but in the event that announced the change.
    """

    def __init__(
        self,
        inbox_gateway: InboxGateway,
        user_query_gateway: UserQueryGateway,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._inbox_gateway: Final[InboxGateway] = inbox_gateway
        self._user_query_gateway: Final[UserQueryGateway] = user_query_gateway
        self._dispatcher: Final[NotificationDispatcher] = dispatcher

    @override
    async def handle(
        self,
        command: NotifyDeliveryAddressChangedCommand,
    ) -> NotificationOutcome:
        claimed = await self._inbox_gateway.claim(
            command.message_id,
            OrderDeliveryAddressChanged.__name__,
        )

        if not claimed:
            logger.info(
                "notifications: message %s was handled before, dropping",
                command.message_id,
            )
            return NotificationOutcome.duplicate()

        customer = await self._user_query_gateway.read_by_id(
            UserId(command.customer_id),
        )

        if customer is None:
            logger.warning(
                "notifications: order %s belongs to unknown user %s",
                command.order_number,
                command.customer_id,
            )
            return NotificationOutcome(delivered=0, skipped=1)

        outcome = await self._dispatcher.dispatch_to_all(
            [customer],
            NotificationText(
                key=text_keys.NOTIFICATION_ORDER_ADDRESS_CHANGED,
                args={
                    "number": command.order_number,
                    "old_address": command.old_address,
                    "new_address": command.new_address,
                },
            ),
        )

        logger.info(
            "notifications: order %s changed address, sent=%d skipped=%d",
            command.order_number,
            outcome.delivered,
            outcome.skipped,
        )
        return outcome
