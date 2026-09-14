from typing import Final

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from dishka import FromDishka

from goldy.application.common.mediator.sender import Sender
from goldy.presentation.telegram.filters.chat import ChatTypeFilter
from goldy.presentation.telegram.handlers.catalog.callbacks import (
    exact_match_product_id,
)
from goldy.presentation.telegram.handlers.catalog.getters import (
    PRODUCT_ID_KEY,
    TERM_KEY,
)
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates

router: Final[Router] = Router(name="catalog")
router.message.filter(ChatTypeFilter(allowed_chat_types=[ChatType.PRIVATE]))


@router.message(Command("catalog"))
async def handle_catalog(_message: Message, dialog_manager: DialogManager) -> None:
    """Opens the catalog at the top of the tree.

    ``RESET_STACK`` for the reason ``/me`` uses it: somebody who types a
    command while halfway through something else is asking to be taken
    somewhere, not to have a second dialog stacked on the one they left.
    """
    await dialog_manager.start(CatalogStates.CATEGORIES, mode=StartMode.RESET_STACK)


@router.message(Command("search"))
async def handle_search(
    _message: Message,
    command: CommandObject,
    dialog_manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Searches from the command line, and opens a card when it can.

    ``/search`` on its own is an invitation, so the dialog opens on the prompt.
    ``/search 40-1234`` is somebody who already knows what they want, and the
    promise the design makes them is an answer in one message — so the article
    is resolved here, before any screen is drawn, and a term that matched
    exactly one article opens that product's card instead of a list of one.

    Resolving it costs one extra read on this path only, and the screen that
    opens fetches what it draws either way.

    A term too short to index is refused by the application layer and rendered
    by the error handler, which is why nothing is validated here.
    """
    term = (command.args or "").strip()

    if not term:
        await dialog_manager.start(CatalogStates.SEARCH, mode=StartMode.RESET_STACK)
        return

    product_id = await exact_match_product_id(sender, term)
    data: dict[str, str] = {TERM_KEY: term}
    state = CatalogStates.RESULTS

    if product_id is not None:
        data[PRODUCT_ID_KEY] = product_id
        state = CatalogStates.CARD

    await dialog_manager.start(state, data=data, mode=StartMode.RESET_STACK)
