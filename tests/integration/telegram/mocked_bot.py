"""A Telegram that records what the bot said and answers plausibly.

``aiogram_tests.MockedBot`` gets the hard part right — a ``BaseSession`` that
never opens a socket — but its ``auto_mock_success`` answers every call with
``Response(ok=True, result=None)``. aiogram-dialog cannot survive that: it
combines the *returned* message into the dialog window, reading
``message_result.message_id``, so every window in this bot would die on
``AttributeError`` before a single assertion ran.

Queueing a result per call through ``add_result_for`` would work and would be
unreadable — showing one dialog window is a ``deleteMessage`` and a
``sendMessage`` whose order depends on whether the window carries a reply
keyboard, and a test would fail on a wrongly sized queue rather than on behaviour.

So the session answers by method instead: a message where Telegram returns a
message, ``True`` where it returns a flag, and a loud refusal for anything this
bot has never been seen to call — because a silent ``None`` there is exactly the
failure this module exists to remove.
"""

from datetime import UTC, datetime
from itertools import count
from typing import Any, Final, cast, final, override

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, InlineKeyboardMarkup, Message
from aiogram_tests.mocked_bot import MockedBot, MockedSession

FIRST_MESSAGE_ID: Final[int] = 1000
SENT_AT: Final[datetime] = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class UnexpectedTelegramCallError(AssertionError):
    """The bot called a method this fake has no answer for.

    Raised rather than answered with ``None`` on purpose: a new widget that
    sends a photo should fail here, naming the method, instead of failing three
    frames deep inside aiogram-dialog.
    """


@final
class RecordingSession(MockedSession):
    """Keeps every outgoing call and answers it the way Telegram would."""

    def __init__(self) -> None:
        super().__init__()
        self.exchanges: Final[list[tuple[TelegramMethod[Any], Any]]] = []
        self._message_ids: Final[count[int]] = count(FIRST_MESSAGE_ID)

    @override
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.closed = False
        result = _answer(method, next(self._message_ids))
        self.exchanges.append((method, result))
        return cast("TelegramType", result)

    def forget(self) -> None:
        self.exchanges.clear()


@final
class RecordingBot(MockedBot):
    """The production ``Bot`` class, talking to :class:`RecordingSession`.

    A real ``Bot`` and not a stand-in, because everything downstream — the
    dispatcher, the dialogs, aiogram's own context middleware — is the real
    thing and expects one.
    """

    TOKEN: Final[str] = "42:TEST"

    def __init__(self) -> None:
        super().__init__(auto_mock_success=False, token=self.TOKEN)
        self.session = RecordingSession()

    @property
    def recorded(self) -> RecordingSession:
        """The session, typed — ``Bot.session`` is declared as a ``BaseSession``."""
        return self.session


def _answer(method: TelegramMethod[Any], message_id: int) -> Any:
    """What Telegram would have returned for this call."""
    if isinstance(method, SendMessage):
        return _message(message_id, method.chat_id, method.text, method.reply_markup)

    if isinstance(method, EditMessageText):
        return _message(
            method.message_id if method.message_id is not None else message_id,
            method.chat_id,
            method.text,
            method.reply_markup,
        )

    if isinstance(method, EditMessageReplyMarkup):
        return _message(
            method.message_id if method.message_id is not None else message_id,
            method.chat_id,
            None,
            method.reply_markup,
        )

    if isinstance(method, DeleteMessage | AnswerCallbackQuery):
        return True

    msg = (
        f"Nothing here knows what {type(method).__name__} returns. "
        f"Add it to `_answer` next to the method it resembles."
    )
    raise UnexpectedTelegramCallError(msg)


def _message(
    message_id: int,
    chat_id: int | str | None,
    text: str | None,
    reply_markup: Any,
) -> Message:
    return Message(
        message_id=message_id,
        date=SENT_AT,
        chat=Chat(id=int(chat_id or 0), type=ChatType.PRIVATE.value),
        text=text,
        reply_markup=(
            reply_markup if isinstance(reply_markup, InlineKeyboardMarkup) else None
        ),
    )
