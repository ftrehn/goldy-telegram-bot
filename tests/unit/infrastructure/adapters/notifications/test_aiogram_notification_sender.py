"""Which answers from Telegram are failures and which are just answers.

The distinction is the whole adapter. "Forbidden" and "chat not found" mean the
same thing next time, so retrying costs a redelivery and gains nothing — they
come back as False and the batch moves on. A timeout or a 5xx might well
succeed on the next attempt, so they become an ``InfrastructureError`` and the
message goes back on the queue.

Getting it the wrong way round is not a small bug either way. Raising on
"forbidden" would announce one order to the same managers over and over;
swallowing a timeout would lose the notification silently.
"""

from typing import Final, cast, override

import pytest
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.methods import SendMessage, TelegramMethod

from goldy.application.common.ports.notifications import OutgoingNotification
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.infrastructure.adapters.notifications.aiogram_notification_sender import (
    AiogramNotificationSender,
)
from goldy.infrastructure.errors import NotificationSendError

TOKEN: Final[str] = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
CHAT_ID: Final[str] = "424242"


class StubBot(Bot):
    """A ``Bot`` that answers calls from a script instead of over the network.

    Subclassed rather than mocked because the adapter is written against
    ``send_message``, and the thing worth pinning down is which exception types
    it lets past — which only a real aiogram exception hierarchy can show.
    """

    def __init__(self, failure: Exception | None = None) -> None:
        super().__init__(token=TOKEN)
        self.failure: Exception | None = failure
        self.calls: list[SendMessage] = []

    @override
    async def __call__[T](
        self,
        method: TelegramMethod[T],
        request_timeout: int | None = None,
    ) -> T:
        """Records the call and then answers, or fails, as the test asked.

        The answer itself is never read: the adapter cares whether the call
        raised, not what came back, so there is nothing to build a ``Message``
        out of and nothing that would be exercised by building one.
        """
        if isinstance(method, SendMessage):
            self.calls.append(method)

        if self.failure is not None:
            raise self.failure

        return cast("T", None)


def a_notification(external_id: str = CHAT_ID) -> OutgoingNotification:
    return OutgoingNotification(external_id=external_id, text="Заказ 1042 — отгружен.")


def test_the_sender_speaks_for_telegram_and_says_so() -> None:
    """The dispatcher asks before writing, which is how ``notify_via`` is kept."""
    assert AiogramNotificationSender(StubBot()).platform is MessengerPlatform.TELEGRAM


async def test_a_delivered_message_is_reported_delivered() -> None:
    bot = StubBot()

    delivered = await AiogramNotificationSender(bot).send(a_notification())

    assert delivered
    assert [call.chat_id for call in bot.calls] == [int(CHAT_ID)]


async def test_the_rendered_text_is_passed_through_untouched() -> None:
    """Nothing is escaped, because nothing is marked up.

    The notifier sends plain text: addresses, names and cancellation reasons
    are typed by people, and with HTML on one ``<`` in an address is an
    unsupported tag that makes Telegram refuse the whole message. The parse
    mode is left at the bot's default, which is where that decision lives —
    see ``test_the_notifier_bot_has_no_default_parse_mode``.
    """
    bot = StubBot()
    notification = a_notification()

    await AiogramNotificationSender(bot).send(notification)

    assert [call.text for call in bot.calls] == [notification.text]


def test_the_notifier_bot_has_no_default_parse_mode() -> None:
    """The other half of the plain-text decision, where it is actually made.

    ``make_notifier_bot`` builds a ``Bot`` with no ``DefaultBotProperties``, so
    the sentinel every method carries resolves to "no parse mode". Setting one
    there would quietly turn every notification into markup.
    """
    assert StubBot().default.parse_mode is None


@pytest.mark.parametrize(
    "refusal",
    (
        TelegramForbiddenError(
            method=SendMessage(chat_id=1, text="x"), message="bot was blocked"
        ),
        TelegramBadRequest(
            method=SendMessage(chat_id=1, text="x"), message="chat not found"
        ),
    ),
)
async def test_an_unreachable_account_is_reported_not_raised(refusal: Exception) -> None:
    delivered = await AiogramNotificationSender(StubBot(refusal)).send(a_notification())

    assert not delivered


async def test_a_transport_failure_is_wrapped_and_raised() -> None:
    """Worth another attempt, so it has to reach the consumer."""
    failure = TelegramNetworkError(
        method=SendMessage(chat_id=1, text="x"), message="timeout"
    )

    with pytest.raises(NotificationSendError):
        await AiogramNotificationSender(StubBot(failure)).send(a_notification())


async def test_an_account_id_that_is_not_a_chat_id_is_an_error() -> None:
    """``ExternalAccountId`` is text because MAX's is; Telegram's is a number."""
    with pytest.raises(NotificationSendError):
        await AiogramNotificationSender(StubBot()).send(a_notification("not-a-number"))
