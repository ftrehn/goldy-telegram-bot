from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.filters.staff import IsStaffFilter
from goldy.presentation.telegram.handlers.manage_orders.states import ManageOrdersStates

router: Final[Router] = Router(name="manage_orders")
router.message.filter(
    ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]),
    IsStaffFilter(),
)


@router.message(Command("manage_orders"))
async def handle_manage_orders(
    _message: Message,
    dialog_manager: DialogManager,
) -> None:
    """Opens the staff order queue.

    The staff filter sits on the router, so a customer typing this falls
    through to the fallback and is told the command is unknown — rather than
    being refused, which would confirm it exists. That is why the command is
    also kept out of the published command menu: ``help-staff`` exists to stop
    a customer being told about staff commands, and a menu listing this one
    would walk straight around that.

    Convenience, not security. Every query and command behind this dialog
    authorises against the aggregate, where it cannot be bypassed.
    """
    await dialog_manager.start(ManageOrdersStates.QUEUE, mode=StartMode.RESET_STACK)
