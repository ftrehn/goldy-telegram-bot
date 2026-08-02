"""What the bot said, as a test wants to read it.

Wraps the recording session in questions rather than in a list of raw calls:
a test asks for the text somebody was shown, or the buttons they were offered,
and never for ``session.exchanges[-1][0].reply_markup.inline_keyboard[0][0]``.

Typed on the method class, so ``sent.only(SendMessage).text`` is checked rather
than being an ``Any`` that mypy waves through — which matters here, since
``--mypy`` runs over these tests.
"""

from typing import Any, Final, final

from aiogram.methods import EditMessageText, SendMessage, TelegramMethod
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from tests.integration.telegram.mocked_bot import RecordingSession


class NothingWasSentError(AssertionError):
    """The bot answered nothing at all, which is almost never intended."""


class ButtonNotOfferedError(AssertionError):
    """The test pressed a button the last window did not show."""


@final
class SentCalls:
    """Every API call the bot made while handling the updates fed so far."""

    def __init__(self, session: RecordingSession) -> None:
        self._session: Final[RecordingSession] = session

    def all[MethodT: TelegramMethod[Any]](
        self,
        method: type[MethodT],
    ) -> tuple[MethodT, ...]:
        return tuple(
            call for call, _ in self._session.exchanges if isinstance(call, method)
        )

    def last[MethodT: TelegramMethod[Any]](self, method: type[MethodT]) -> MethodT:
        calls = self.all(method)
        if not calls:
            raise NothingWasSentError(self._nothing_matched(method))
        return calls[-1]

    def only[MethodT: TelegramMethod[Any]](self, method: type[MethodT]) -> MethodT:
        """The single call of this kind, refusing when there was more than one.

        Sharper than ``last`` for the cases that are about restraint — the auth
        gate answering once and stopping, rather than answering and then letting
        the handler answer too.
        """
        calls = self.all(method)
        if not calls:
            raise NothingWasSentError(self._nothing_matched(method))
        if len(calls) > 1:
            msg = (
                f"Expected one {method.__name__}, got {len(calls)}: "
                f"{[_describe(call) for call in calls]}"
            )
            raise AssertionError(msg)
        return calls[0]

    def texts(self) -> tuple[str, ...]:
        """Everything the person was shown, sent and edited alike, in order."""
        return tuple(
            call.text
            for call, _ in self._session.exchanges
            if isinstance(call, SendMessage | EditMessageText) and call.text is not None
        )

    def last_text(self) -> str:
        texts = self.texts()
        if not texts:
            msg = "The bot said nothing."
            raise NothingWasSentError(msg)
        return texts[-1]

    def buttons(self) -> tuple[str, ...]:
        """The labels on the last window, read the way a person reads them."""
        return tuple(button.text for button in self._last_buttons())

    def callback_data_for(self, label: str) -> str:
        """What pressing the button with this label would send back."""
        for button in self._last_buttons():
            if button.text == label and button.callback_data is not None:
                return button.callback_data

        msg = f"No button labelled {label!r}. The window offered: {list(self.buttons())}"
        raise ButtonNotOfferedError(msg)

    def last_message_id(self) -> int:
        """The id of the message the bot most recently put on screen.

        Read from what the fake transport *answered*, not from the request:
        that is the id aiogram-dialog stored, and pressing a button on any other
        one would land on a window the dialog does not know about.
        """
        for _, result in reversed(self._session.exchanges):
            if isinstance(result, Message):
                return result.message_id

        msg = "The bot never put a message on screen."
        raise NothingWasSentError(msg)

    def forget(self) -> None:
        self._session.forget()

    def _last_buttons(self) -> tuple[InlineKeyboardButton, ...]:
        for call, _ in reversed(self._session.exchanges):
            markup = getattr(call, "reply_markup", None)
            if isinstance(markup, InlineKeyboardMarkup):
                return tuple(button for row in markup.inline_keyboard for button in row)

        msg = "No window with inline buttons was shown."
        raise NothingWasSentError(msg)

    def _nothing_matched(self, method: type[TelegramMethod[Any]]) -> str:
        made = [_describe(call) for call, _ in self._session.exchanges]
        return f"No {method.__name__} was sent. The bot called: {made or 'nothing'}"


def _describe(call: TelegramMethod[Any]) -> str:
    text = getattr(call, "text", None)
    return type(call).__name__ if text is None else f"{type(call).__name__}({text!r})"
