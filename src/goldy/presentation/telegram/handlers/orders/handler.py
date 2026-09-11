from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.orders.states import OrdersStates

router: Final[Router] = Router(name="orders")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("orders"))
async def handle_orders(_message: Message, dialog_manager: DialogManager) -> None:
    """Opens the order history.

    ``RESET_STACK`` for the reason ``/me`` uses it: somebody who typed this
    halfway through the catalog means "show me my orders", not "stack a history
    on top of whatever I was browsing". It also matters here specifically —
    this router is attached ahead of the dialogs, so the command is claimed
    even while a catalog window is waiting for a search term.
    """
    await dialog_manager.start(OrdersStates.LIST, mode=StartMode.RESET_STACK)
