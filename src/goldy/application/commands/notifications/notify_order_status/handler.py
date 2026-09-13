import logging
from typing import Final, override

from goldy.application.commands.notifications.dispatcher import NotificationDispatcher
from goldy.application.commands.notifications.notify_order_status.command import (
    NotifyOrderStatusChangedCommand,
)
from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.notifications import (
    InboxGateway,
    OrderStatusChangedNotification,
)
from goldy.application.common.ports.users import UserQueryGateway
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotifyOrderStatusChangedHandler(
    CommandHandler[NotifyOrderStatusChangedCommand, NotificationOutcome],
):
    """Tells the buyer where their order has got to.

    No order is read. Everything the message says — the number, the new status
    and the reason a cancellation carries — is in the event, and reading the
    document to repeat what the fact already stated would only add a way for
    the two to disagree when the order moves again in between.

    The customer is read, though, because whom to write to and in what language
    is theirs to decide and lives on their record. If they are blocked, or
    their notification target is a messenger this worker cannot reach, nothing
    is sent and the message is still marked handled: those are answers, not
    failures, and redelivering would not change them.
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
        command: NotifyOrderStatusChangedCommand,
    ) -> NotificationOutcome:
        claimed = await self._inbox_gateway.claim(command.message_id, command.event_type)

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
            OrderStatusChangedNotification(
                number=command.order_number,
                status=command.new_status,
                reason=command.reason,
            ),
        )

        logger.info(
            "notifications: order %s is now %s, sent=%d skipped=%d",
            command.order_number,
            command.new_status,
            outcome.delivered,
            outcome.skipped,
        )
        return outcome
