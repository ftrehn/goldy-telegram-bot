import asyncio
import logging
from collections.abc import Iterable
from typing import Final

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.commands.notifications.senders import NotificationSenders
from goldy.application.common.ports.notifications import (
    Notification,
    NotificationRenderer,
    OutgoingNotification,
)
from goldy.application.common.services.notification_recipient_resolver import (
    NotificationRecipient,
    NotificationRecipientResolver,
)
from goldy.application.common.views.user import UserView
from goldy.application.error import NotificationUndeliverableError

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotificationDispatcher:
    """Renders one notification per person, in their language, and sends it.

    A collaborator shared by the notification handlers rather than three
    collaborators injected into each. The trio is always used together —
    whom to write to, what the words are in their language, and which sender
    speaks their messenger — and every handler would otherwise repeat the
    same few lines.

    Two failures are answers, and one is not. A person who cannot be reached
    is counted as skipped and the batch goes on, because a batch of managers
    must not be abandoned when one of them has blocked the bot, and a raised
    exception would send the broker message back for redelivery — which would
    write to everyone the batch had already reached a second time. A messenger
    this process has no sender for is not an answer: it is a deployment that
    let somebody choose a channel nobody serves, and it raises.
    """

    def __init__(
        self,
        senders: NotificationSenders,
        renderer: NotificationRenderer,
        recipient_resolver: NotificationRecipientResolver,
    ) -> None:
        self._senders: Final[NotificationSenders] = senders
        self._renderer: Final[NotificationRenderer] = renderer
        self._recipient_resolver: Final[NotificationRecipientResolver] = (
            recipient_resolver
        )

    async def dispatch_to_all(
        self,
        users: Iterable[UserView],
        notification: Notification,
    ) -> NotificationOutcome:
        """Writes the same notification to everyone it is meant for.

        The text is rendered per person rather than once: two managers can read
        different languages, and the whole point of carrying a typed message
        this far is that the wording is chosen by the reader.

        The sends go out together rather than one after another. They are
        independent calls to a messenger, so three managers wait for one
        round trip and not for three; they are still awaited, because the
        handler's transaction — and with it the inbox claim — must not commit
        before the messages have actually left.
        """
        recipients = [self._recipient_resolver.resolve(user) for user in users]
        deliveries = await asyncio.gather(
            *(
                self.dispatch(recipient, notification)
                for recipient in recipients
                if recipient is not None
            ),
        )
        delivered = sum(1 for reached in deliveries if reached)

        return NotificationOutcome(
            delivered=delivered,
            skipped=len(recipients) - delivered,
        )

    async def dispatch(
        self,
        recipient: NotificationRecipient,
        notification: Notification,
    ) -> bool:
        """True when the message reached the account, False when it could not.

        Raises:
            NotificationChannelUnavailableError: no sender in this process
                speaks the recipient's messenger.
        """
        sender = self._senders.for_platform(recipient.platform)
        body = self._renderer.render(notification, recipient.locale)

        try:
            await sender.send(
                OutgoingNotification(external_id=recipient.external_id, text=body),
            )
        except NotificationUndeliverableError:
            logger.info(
                "notifications: %s cannot be reached on %s, skipping",
                recipient.user_id,
                recipient.platform.value,
            )
            return False

        return True
