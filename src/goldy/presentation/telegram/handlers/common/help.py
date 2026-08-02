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

router: Final[Router] = Router(name="help")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("help"))
async def handle_help(message: Message, i18n: I18nContext, user: UserView) -> None:
    """Lists what this person can do — and only what this person can do.

    ``user`` is never ``None`` here: the auth gate lets nothing but the
    registration flow past without one, so a handler behind it can take a
    registered person as given.
    """
    key = text_keys.HELP_STAFF if user.is_staff else text_keys.HELP_CUSTOMER

    await message.answer(i18n.get(key), reply_markup=remove_keyboard())
