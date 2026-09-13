import logging
from typing import Final, final, override

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)

from goldy.application.common.ports.notifications import (
    NotificationSender,
    OutgoingNotification,
)
from goldy.application.error import NotificationUndeliverableError
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.infrastructure.errors import NotificationSendError

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class AiogramNotificationSender(NotificationSender):
    """Writes to a Telegram account with the Bot API.

    The worker has a ``Bot`` of its own rather than reaching for the one the
    dispatcher runs on, because the two are different processes; what they
    share is the token, so the messages arrive from the account the customer
    already talks to.

    Plain text, no ``parse_mode``. Everything interesting in these messages —
    a delivery address, a recipient's name, a cancellation reason — is typed by
    a person, and turning HTML on would mean escaping every one of them or
    losing a notification to an unbalanced ``<``.

    Two answers from Telegram mean the account is closed to us. ``Forbidden``
    is the person having blocked the bot or deleted their account, and ``Bad
    Request`` covers a chat that no longer exists: retrying either produces
    the same answer forever, so they become ``NotificationUndeliverableError``
    and the dispatcher moves on to the next recipient. Everything else — a
    timeout, a flood wait, a 5xx — becomes ``NotificationSendError``, because
    the broker redelivering the message is exactly the right response to it.

    Request-scoped like the gateways, not a singleton. It holds nothing but a
    reference to the process-wide ``Bot``, so building one per message costs
    nothing, and a sender that lived for the whole process would be one more
    object whose lifetime is not the request's for no reason.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot: Final[Bot] = bot

    @property
    @override
    def platform(self) -> MessengerPlatform:
        return MessengerPlatform.TELEGRAM

    @override
    async def send(self, notification: OutgoingNotification) -> None:
        """Writes the message to the account, or says why it could not.

        The stored id is text because ``ExternalAccountId`` has to hold MAX's
        too; Telegram hands its out as a number, and the conversion back
        happens here — at the one place that knows the id is Telegram's.

        Raises:
            NotificationUndeliverableError: the account is closed to us, or the
                stored id is not a Telegram chat id at all.
            NotificationSendError: Telegram could not be reached, and a later
                attempt may well succeed.
        """
        try:
            chat_id = int(notification.external_id)
        except ValueError as exc:
            msg = f"Telegram account id {notification.external_id!r} is not a chat id."
            raise NotificationUndeliverableError(msg) from exc

        try:
            await self._bot.send_message(chat_id=chat_id, text=notification.text)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.exception(
                "notifications: telegram account %s is unreachable",
                notification.external_id,
            )
            msg = f"Telegram account {notification.external_id} cannot be written to."
            raise NotificationUndeliverableError(msg) from exc
        except Exception as exc:
            msg = f"Failed to notify telegram account {notification.external_id}."
            raise NotificationSendError(msg) from exc

        logger.debug("notifications: wrote to %s", notification.external_id)
