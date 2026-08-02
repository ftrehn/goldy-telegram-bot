"""The people who write to the bot.

A persona ties together the two identities that must agree for anything to
work: the ``UserId`` the database knows and the Telegram account id the update
carries. ``TelegramIdentityProvider`` resolves the second into the first, so a
test that got them out of step would not fail — it would quietly be told to
register, which reads like a bug in the handler under test.

Keeping both on one object makes that impossible to get wrong, and lets a test
with two people in it say *whose* update this is instead of juggling numbers.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Final, final
from uuid import UUID

from aiogram.enums import ChatType
from aiogram.types import (
    CallbackQuery,
    Chat,
    Contact,
    Message,
    Update,
    User as TelegramUser,
)

from goldy.domain.users.values.user_id import UserId

SENT_AT: Final[datetime] = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
GROUP_CHAT_ID: Final[int] = -1001234567890
CHAT_INSTANCE: Final[str] = "test-chat-instance"

_UPDATE_IDS: Final[count[int]] = count(1)
_INCOMING_MESSAGE_IDS: Final[count[int]] = count(1)


@final
@dataclass(frozen=True, slots=True)
class Person:
    """Somebody with an account on Telegram and a row in our database."""

    user_id: UserId
    telegram_id: int
    phone_number: str
    first_name: str = "Данил"
    last_name: str | None = "Ковалев"
    username: str | None = "c3equalz"
    language_code: str = "ru"

    @property
    def account(self) -> TelegramUser:
        return TelegramUser(
            id=self.telegram_id,
            is_bot=False,
            first_name=self.first_name,
            last_name=self.last_name,
            username=self.username,
            language_code=self.language_code,
        )

    @property
    def list_label(self) -> str:
        """How the admin list writes this person on their button.

        Mirrors ``admin.getters._label`` rather than importing it: a test
        presses what a person can read, and if the two ever disagree the test
        should fail — which is the only reason to spell it out twice.
        """
        name = (
            self.first_name
            if self.last_name is None
            else f"{self.first_name} {self.last_name}"
        )
        return f"{name} · {self.phone_number}"

    @property
    def chat(self) -> Chat:
        """Their private chat with the bot.

        Same id as the account, which is what Telegram does for private chats —
        and getting it wrong would make the FSM key disagree with the identity.
        """
        return Chat(id=self.telegram_id, type=ChatType.PRIVATE.value)

    def says(self, text: str) -> Update:
        return _update(message=self._message(text=text))

    def shares_contact(
        self,
        phone_number: str | None = None,
        owner_id: int | None = None,
    ) -> Update:
        """Sends a contact card.

        ``owner_id`` defaults to this person, which is the only case Telegram
        produces for the "share my number" button. A test forges a different one
        to check the ownership guard — the card of somebody else is exactly what
        an attacker forwards from their address book.
        """
        contact = Contact(
            phone_number=phone_number if phone_number is not None else self.phone_number,
            first_name=self.first_name,
            last_name=self.last_name,
            user_id=owner_id if owner_id is not None else self.telegram_id,
        )
        return _update(message=self._message(contact=contact))

    def shares_contact_without_number(self) -> Update:
        contact = Contact(
            phone_number="",
            first_name=self.first_name,
            user_id=self.telegram_id,
        )
        return _update(message=self._message(contact=contact))

    def says_in_a_group(self, text: str) -> Update:
        """The same words, in a chat where an order has no business being read."""
        return _update(
            message=Message(
                message_id=next(_INCOMING_MESSAGE_IDS),
                date=SENT_AT,
                chat=Chat(id=GROUP_CHAT_ID, type=ChatType.SUPERGROUP.value),
                from_user=self.account,
                text=text,
            ),
        )

    def presses(self, callback_data: str, message_id: int) -> Update:
        """Taps an inline button on the window the bot last showed them."""
        return _update(
            callback_query=CallbackQuery(
                id=f"cb-{next(_UPDATE_IDS)}",
                from_user=self.account,
                chat_instance=CHAT_INSTANCE,
                data=callback_data,
                message=Message(
                    message_id=message_id,
                    date=SENT_AT,
                    chat=self.chat,
                    from_user=self.account,
                ),
            ),
        )

    def _message(
        self, text: str | None = None, contact: Contact | None = None
    ) -> Message:
        return Message(
            message_id=next(_INCOMING_MESSAGE_IDS),
            date=SENT_AT,
            chat=self.chat,
            from_user=self.account,
            text=text,
            contact=contact,
        )


def a_stranger(telegram_id: int = 999_000_001) -> Person:
    """Somebody Telegram knows and we do not.

    Carries a ``user_id`` that matches no row, so anything reading it in a test
    is reading a number that was never meant to resolve.
    """
    return Person(
        user_id=UserId(UUID(int=0)),
        telegram_id=telegram_id,
        phone_number="+79990000001",
        first_name="Незнакомец",
        last_name=None,
        username=None,
    )


def _update(
    message: Message | None = None,
    callback_query: CallbackQuery | None = None,
) -> Update:
    return Update(
        update_id=next(_UPDATE_IDS),
        message=message,
        callback_query=callback_query,
    )
