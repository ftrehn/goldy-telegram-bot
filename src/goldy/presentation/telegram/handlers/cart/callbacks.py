from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import ManagedTextInput
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.commands.carts.clear_cart.command import ClearCartCommand
from goldy.application.commands.carts.decrease_cart_line.command import (
    DecreaseCartLineCommand,
)
from goldy.application.commands.carts.remove_cart_line.command import (
    RemoveCartLineCommand,
)
from goldy.application.commands.carts.remove_unavailable_cart_lines.command import (
    RemoveUnavailableCartLinesCommand,
)
from goldy.application.commands.carts.set_cart_line_quantity.command import (
    SetCartLineQuantityCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18N_CONTEXT_KEY
from goldy.presentation.telegram.handlers.cart.getters import (
    PRODUCT_ID_KEY,
    drawn_quantity,
    selected_product_id,
)
from goldy.presentation.telegram.handlers.cart.states import CartStates

LAST_PIECE: int = 1
"""The quantity below which a line stops existing rather than reaching zero."""


async def on_line_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data[PRODUCT_ID_KEY] = item_id
    await manager.switch_to(CartStates.LINE)


@inject
async def on_increased(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Adds one more of what this screen is showing.

    The same command the catalog card sends, because ``+`` here and "add to
    cart" there are the same act — the cart accumulates. It asks the catalog
    whether the product is still on sale, so pressing ``+`` on a line that has
    since been withdrawn is refused with a message rather than silently
    raising a quantity nobody can order.
    """
    await sender.send(AddToCartCommand(product_id=selected_product_id(manager)))


@inject
async def on_decreased(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Takes one piece off, and the whole screen off the last piece.

    Leaving on the last piece is not tidiness. ``decrease_item`` removes a line
    it would otherwise take to zero, so staying here would redraw a position
    that no longer exists — the list is where the person has to end up, and
    getting there by themselves would mean reading "this line is gone" first.
    """
    was_last_piece = drawn_quantity(manager) <= LAST_PIECE

    await sender.send(DecreaseCartLineCommand(product_id=selected_product_id(manager)))

    if was_last_piece:
        await manager.switch_to(CartStates.MAIN)


@inject
async def on_line_removed(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    await sender.send(RemoveCartLineCommand(product_id=selected_product_id(manager)))
    await manager.switch_to(CartStates.MAIN)


@inject
async def on_quantity_typed(
    _message: Message,
    _widget: ManagedTextInput[int],
    manager: DialogManager,
    quantity: int,
    sender: FromDishka[Sender],
) -> None:
    """Sets the line to the number that was typed.

    Nothing is judged here. ``Quantity`` refuses zero and anything above the
    ceiling, and both refusals reach the person through the one error table, so
    the rule has a single home and the prompt on this screen is the only thing
    that has to agree with it.

    Text that is not a number at all never arrives: the input widget is built
    with ``int`` as its factory and drops what it cannot convert, and the
    window redraws its prompt, which says what to send.
    """
    await sender.send(
        SetCartLineQuantityCommand(
            product_id=selected_product_id(manager),
            quantity=quantity,
        ),
    )
    await manager.switch_to(CartStates.LINE)


@inject
async def on_unavailable_removed(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Sweeps out every line whose product has left the catalog.

    One button rather than a hunt through the list: the customer is not
    choosing which of eight positions is the broken one, they are accepting all
    of them at once so that checkout can proceed.
    """
    await sender.send(RemoveUnavailableCartLinesCommand())
    await manager.switch_to(CartStates.MAIN)


@inject
async def on_cart_cleared(
    callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Empties the cart, and says so where the person is looking.

    The confirmation is a toast on the button rather than a line in the window,
    because the window behind it has just become "your cart is empty" — which
    is the state, not the news. The two together are what makes an emptied cart
    read as something that was done rather than something that went wrong.
    """
    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]

    await sender.send(ClearCartCommand())
    await callback.answer(i18n.get(text_keys.CART_CLEARED_TOAST))
    await manager.switch_to(CartStates.MAIN)
