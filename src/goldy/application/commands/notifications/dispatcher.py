import logging
from collections.abc import Iterable
from typing import Final

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.commands.notifications.recipients import (
    NotificationRecipient,
    recipient_for,
)
from goldy.application.common.ports.notifications import (
    NotificationRenderer,
    NotificationSender,
    NotificationText,
    OutgoingNotification,
)
from goldy.application.common.views.user import UserView

logger: Final[logging.Logger] = logging.getLogger(__name__)


class NotificationDispatcher:
    """Renders one notification per person, in their language, and sends it.

    A collaborator shared by the notification handlers rather than two
    collaborators injected into each. The pair is always used together — text
    without a language is not a message, and a sender without text has nothing
    to send — and every handler would otherwise repeat the same few lines,
    including the check that keeps a Telegram sender away from a MAX account.

    Nothing here raises because somebody could not be reached. A batch of
    managers must not be abandoned when one of them has blocked the bot, and a
    raised exception would send the broker message back for redelivery — which
    would write to everyone the batch had already reached a second time.
    """

    def __init__(
        self,
        sender: NotificationSender,
        renderer: NotificationRenderer,
    ) -> None:
        self._sender: Final[NotificationSender] = sender
        self._renderer: Final[NotificationRenderer] = renderer

    async def dispatch_to_all(
        self,
        users: Iterable[UserView],
        text: NotificationText,
    ) -> NotificationOutcome:
        """Writes the same notification to everyone it is meant for.

        The text is rendered per person rather than once: two managers can read
        different languages, and the whole point of carrying a key this far is
        that the wording is chosen by the reader.
        """
        delivered = 0
        skipped = 0

        for user in users:
            recipient = recipient_for(user)

            if recipient is None or not await self.dispatch(recipient, text):
                skipped += 1
                continue

            delivered += 1

        return NotificationOutcome(delivered=delivered, skipped=skipped)

    async def dispatch(
        self,
        recipient: NotificationRecipient,
        text: NotificationText,
    ) -> bool:
        """True when the message reached the account, False when it could not.

        The platform check is the notification target being respected rather
        than assumed: somebody who chose to be reached on MAX is not written to
        on Telegram because their Telegram id happens to be on file.
        """
        if recipient.platform is not self._sender.platform:
            logger.info(
                "notifications: %s wants %s, this sender speaks %s — skipping",
                recipient.user_id,
                recipient.platform.value,
                self._sender.platform.value,
            )
            return False

        body = self._renderer.render(text, recipient.locale)

        return await self._sender.send(
            OutgoingNotification(external_id=recipient.external_id, text=body),
        )
