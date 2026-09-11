import operator
from typing import Final

from aiogram import F
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Group, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Format, List

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.paging import paging_row
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.cart.callbacks import (
    on_cart_cleared,
    on_decreased,
    on_increased,
    on_line_removed,
    on_line_selected,
    on_quantity_typed,
    on_unavailable_removed,
)
from goldy.presentation.telegram.handlers.cart.getters import (
    cart_getter,
    line_getter,
    quantity_getter,
)
from goldy.presentation.telegram.handlers.cart.states import CartStates
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates
from goldy.presentation.telegram.handlers.checkout.states import CheckoutStates

CART_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(
            text_keys.CART_TITLE,
            count=F["count"],
            total=Format("{total}"),
            when=~F["is_empty"],
        ),
        List(
            I18NFormat(
                text_keys.CART_LINE,
                position=Format("{item[position]}"),
                name=Format("{item[name]}"),
                quantity=Format("{item[quantity]}"),
                price=Format("{item[price]}"),
                total=Format("{item[total]}"),
                mark=Format("{item[mark]}"),
            ),
            items="lines",
        ),
        I18NFormat(text_keys.CART_SCREEN_EMPTY, when="is_empty"),
        I18NFormat(text_keys.CART_UNAVAILABLE_NOTICE, when="has_unavailable"),
        I18NFormat(text_keys.CART_UNPRICED_NOTICE, when="has_unpriced"),
        Group(
            Select(
                Format("{item[label]}"),
                id="line",
                item_id_getter=operator.itemgetter("product_id"),
                items="lines",
                on_click=on_line_selected,
            ),
            width=1,
        ),
        paging_row(),
        Button(
            I18NFormat(text_keys.CART_REMOVE_UNAVAILABLE_BUTTON),
            id="remove_unavailable",
            on_click=on_unavailable_removed,
            when="has_unavailable",
        ),
        Start(
            I18NFormat(text_keys.CART_CHECKOUT_BUTTON),
            id="checkout",
            state=CheckoutStates.ADDRESS,
            when="can_checkout",
        ),
        SwitchTo(
            I18NFormat(text_keys.CART_CLEAR_BUTTON),
            id="clear",
            state=CartStates.CLEAR_CONFIRM,
            when=~F["is_empty"],
        ),
        Start(
            I18NFormat(text_keys.CART_CONTINUE_BUTTON),
            id="to_catalog",
            state=CatalogStates.CATEGORIES,
            mode=StartMode.RESET_STACK,
        ),
        Cancel(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close_cart"),
        state=CartStates.MAIN,
        getter=cart_getter,
    ),
    Window(
        I18NFormat(
            text_keys.CART_LINE,
            position=Format("{position}"),
            name=Format("{name}"),
            quantity=Format("{quantity}"),
            price=Format("{price}"),
            total=Format("{total}"),
            mark=Format("{mark}"),
            when="found",
        ),
        I18NFormat(text_keys.CART_LINE_NOT_FOUND, when=~F["found"]),
        Row(
            Button(
                I18NFormat(text_keys.CART_MINUS_BUTTON),
                id="minus",
                on_click=on_decreased,
                when="found",
            ),
            Button(
                I18NFormat(text_keys.CART_PLUS_BUTTON),
                id="plus",
                on_click=on_increased,
                when="found",
            ),
        ),
        Row(
            SwitchTo(
                I18NFormat(text_keys.CART_QUANTITY_BUTTON),
                id="quantity",
                state=CartStates.QUANTITY,
                when="found",
            ),
            Button(
                I18NFormat(text_keys.CART_REMOVE_BUTTON),
                id="remove_line",
                on_click=on_line_removed,
                when="found",
            ),
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_cart",
            state=CartStates.MAIN,
        ),
        state=CartStates.LINE,
        getter=line_getter,
    ),
    Window(
        I18NFormat(text_keys.CART_QUANTITY_PROMPT, max=F["max"]),
        TextInput[int](
            id="quantity_input",
            type_factory=int,
            on_success=on_quantity_typed,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_line",
            state=CartStates.LINE,
        ),
        state=CartStates.QUANTITY,
        getter=quantity_getter,
    ),
    Window(
        I18NFormat(text_keys.CART_CLEAR_CONFIRM),
        Button(
            I18NFormat(text_keys.COMMON_CONFIRM_BUTTON),
            id="clear_confirmed",
            on_click=on_cart_cleared,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_CANCEL_BUTTON),
            id="clear_cancelled",
            state=CartStates.MAIN,
        ),
        state=CartStates.CLEAR_CONFIRM,
    ),
)
"""The cart, one line of it, a keypad and the confirmation before emptying it.

The list is drawn by ``List`` over the rows the getter formatted, and the
keyboard under it is one button per line. Both read the same ``lines`` entry, so
the number in front of a button is the number in front of the row above it —
which is the only thing tying a button labelled with a truncated name to the
line it acts on.

Both show one page rather than the whole cart, which a cart of forty positions
needs: that is four thousand characters of text and forty buttons, and Telegram
refuses a message over either limit outright. The button that opens a line
carries the 1C reference of its product in its callback data, which is why its
id is four characters long — the whole of that data may not exceed 64 bytes,
and everything spent on a widget id is taken off what is left for a product
reference.

"Checkout" is a plain ``Start``: the cart stays on the stack underneath, so
backing out of the order lands on it with everything still in place. "To the
catalog" is the opposite and resets the stack, because it means the same as
typing ``/catalog`` — going back to browsing rather than stacking a catalog on
top of a cart that a later ``Cancel`` would drop back into.
"""
