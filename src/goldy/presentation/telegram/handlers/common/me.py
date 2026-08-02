from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_i18n import I18nContext

from goldy.application.common.views.user import UserView
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.keyboards import remove_keyboard
from goldy.presentation.telegram.filters.chat import ChatTypeFilter

router: Final[Router] = Router(name="me")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("me"))
async def handle_me(message: Message, i18n: I18nContext, user: UserView) -> None:
    """Shows the profile as the bot holds it.

    Reads the user the auth gate already loaded rather than sending
    ``GetCurrentUserQuery``: the gate has to load them anyway to decide whether
    this update is allowed at all, and asking again would be a second trip to
    the database to render what is already in hand.

    Role and language are rendered by Fluent selectors, so the words for them
    live with the other translations instead of in a lookup table here.
    """
    full_name = (
        user.first_name
        if user.last_name is None
        else f"{user.first_name} {user.last_name}"
    )

    await message.answer(
        i18n.get(
            text_keys.ME_PROFILE,
            name=full_name,
            phone=user.phone_number,
            role=user.role,
            locale=user.locale,
            notify=user.notify_via,
        ),
        reply_markup=remove_keyboard(),
    )
