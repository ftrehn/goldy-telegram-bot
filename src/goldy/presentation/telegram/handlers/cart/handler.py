from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.cart.states import CartStates

router: Final[Router] = Router(name="cart")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("cart"))
async def handle_cart(_message: Message, dialog_manager: DialogManager) -> None:
    """Opens the cart.

    ``RESET_STACK`` for the reason ``/me`` uses it: somebody typing ``/cart``
    halfway through the catalog means "show me my cart", not "stack a cart on
    top of whatever I was doing". It also keeps the stack from growing every
    time a person alternates between browsing and checking what they have.

    This works at all only because the feature routers are attached before the
    dialogs. A dialog window waiting on typed input would otherwise swallow
    ``/cart`` as a search term, and the command would answer from inside the
    catalog exactly when it is most wanted.
    """
    await dialog_manager.start(CartStates.MAIN, mode=StartMode.RESET_STACK)
