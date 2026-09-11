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

    Two answers from Telegram are not failures. ``Forbidden`` means the person
    blocked the bot or deleted their account, and ``Bad Request`` covers a chat
    that no longer exists: retrying either produces the same answer forever,
    so they are reported as "not delivered" and the batch moves on. Everything
    else — a timeout, a flood wait, a 5xx — becomes an exception, because the
    broker redelivering the message is exactly the right response to it.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot: Final[Bot] = bot

    @property
    @override
    def platform(self) -> MessengerPlatform:
        return MessengerPlatform.TELEGRAM

    @override
    async def send(self, notification: OutgoingNotification) -> bool:
        chat_id = _chat_id(notification.external_id)

        try:
            await self._bot.send_message(chat_id=chat_id, text=notification.text)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info(
                "notifications: telegram account %s is unreachable (%s)",
                notification.external_id,
                exc,
            )
            return False
        except Exception as exc:
            msg = f"Failed to notify telegram account {notification.external_id}."
            raise NotificationSendError(msg) from exc

        logger.debug("notifications: wrote to %s", notification.external_id)
        return True


def _chat_id(external_id: str) -> int:
    """Telegram's own account id, which it hands out as a number.

    Stored as text because ``ExternalAccountId`` has to hold MAX's too, so the
    conversion back happens here — at the one place that knows the id is
    Telegram's.

    Raises:
        NotificationSendError: the stored id is not a number at all.
    """
    try:
        return int(external_id)
    except ValueError as exc:
        msg = f"Telegram account id {external_id!r} is not a chat id."
        raise NotificationSendError(msg) from exc
