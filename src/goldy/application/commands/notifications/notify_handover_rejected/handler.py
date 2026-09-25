import logging
from typing import Final, override

from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_handover_rejected.command import (
    NotifyOrderHandoverRejectedCommand,
)
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.commands.notifications.staff import read_staff
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.notifications import (
    InboxGateway,
    OrderHandoverRejectedNotification,
)
from goldy.application.common.ports.users import UserQueryGateway

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotifyOrderHandoverRejectedHandler(
    CommandHandler[NotifyOrderHandoverRejectedCommand, NotificationOutcome],
):
    """Puts an order the site refused in front of the people who work orders.

    The order is not lost — it stays in the bot with its managers — but it
    will not reach the site or 1C on its own any more, and somebody has to
    know that today rather than when the customer calls.
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
        command: NotifyOrderHandoverRejectedCommand,
    ) -> NotificationOutcome:
        if not await self._inbox_gateway.claim(command.message_id, command.event_type):
            return NotificationOutcome.duplicate()

        outcome = await self._dispatcher.dispatch_to_all(
            await read_staff(self._user_query_gateway),
            OrderHandoverRejectedNotification(
                number=command.order_number,
                code=command.code,
            ),
        )
        logger.info(
            "notifications: refused handover of %s announced, sent=%d skipped=%d",
            command.order_number,
            outcome.delivered,
            outcome.skipped,
        )
        return outcome
