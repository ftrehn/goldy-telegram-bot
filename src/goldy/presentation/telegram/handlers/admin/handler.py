from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.filters.staff import IsStaffFilter
from goldy.presentation.telegram.handlers.admin.states import AdminStates

router: Final[Router] = Router(name="admin")
router.message.filter(
    ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]),
    IsStaffFilter(),
)


@router.message(Command("admin"))
async def handle_admin(_message: Message, dialog_manager: DialogManager) -> None:
    """Opens the admin list.

    The staff filter sits on the router, so a customer typing ``/admin`` falls
    through to the fallback and is told the command is unknown — rather than
    being refused, which would confirm that it exists.

    That filter is convenience, not security: every command behind this dialog
    re-checks authorization against the aggregate, where it cannot be bypassed.
    """
    await dialog_manager.start(AdminStates.USERS, mode=StartMode.RESET_STACK)
