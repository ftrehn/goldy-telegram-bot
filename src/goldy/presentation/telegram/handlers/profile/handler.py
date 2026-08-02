from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.profile.states import ProfileStates

router: Final[Router] = Router(name="profile")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("me"))
async def handle_me(_message: Message, dialog_manager: DialogManager) -> None:
    """Opens the profile.

    ``RESET_STACK`` because ``/me`` is a fresh start: a person who typed it
    while halfway through another dialog means "take me to my profile", not
    "stack a profile on top of whatever I abandoned".
    """
    await dialog_manager.start(ProfileStates.MAIN, mode=StartMode.RESET_STACK)
