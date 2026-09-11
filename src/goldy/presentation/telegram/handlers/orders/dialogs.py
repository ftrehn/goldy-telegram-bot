import operator
from typing import Final

from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Group, Select, SwitchTo
from aiogram_dialog.widgets.text import Format

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.paging import paging_row
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.orders.callbacks import (
    on_address_typed,
    on_cancel_confirmed,
    on_close,
    on_dialog_start,
    on_order_selected,
    on_repeat_confirmed,
)
from goldy.presentation.telegram.handlers.orders.getters import (
    order_card_getter,
    orders_getter,
    repeat_confirm_getter,
    repeat_result_getter,
)
from goldy.presentation.telegram.handlers.orders.states import OrdersStates

ORDERS_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(
            text_keys.ORDERS_TITLE,
            page=Format("{page}"),
            pages=Format("{pages}"),
            total=Format("{total}"),
        ),
        I18NFormat(text_keys.ORDERS_EMPTY, when="is_empty"),
        Group(
            Select(
                Format("{item[0]}"),
                id="order_select",
                item_id_getter=operator.itemgetter(1),
                items="orders",
                on_click=on_order_selected,
            ),
            width=1,
        ),
        paging_row(),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        state=OrdersStates.LIST,
        getter=orders_getter,
    ),
    Window(
        I18NFormat(
            text_keys.ORDER_CARD,
            number=Format("{number}"),
            date=Format("{date}"),
            status=Format("{status}"),
            address=Format("{address}"),
            recipient=Format("{recipient}"),
            phone=Format("{phone}"),
            has_comment=Format("{has_comment}"),
            comment=Format("{comment}"),
            lines=Format("{lines}"),
            total=Format("{total}"),
        ),
        I18NFormat(
            text_keys.ORDER_CARD_NEXT_STEPS,
            when="show_next_steps",
            phone=Format("{phone}"),
        ),
        I18NFormat(
            text_keys.ORDER_CANCELLED_BY,
            when="is_cancelled",
            by=Format("{cancelled_by}"),
        ),
        I18NFormat(
            text_keys.ORDER_CANCELLATION_REASON,
            when="has_reason",
            reason=Format("{reason}"),
        ),
        SwitchTo(
            I18NFormat(text_keys.ORDER_REPEAT_BUTTON),
            id="repeat_order",
            state=OrdersStates.REPEAT_CONFIRM,
        ),
        SwitchTo(
            I18NFormat(text_keys.ORDER_EDIT_ADDRESS_BUTTON),
            id="edit_address",
            state=OrdersStates.EDIT_ADDRESS,
            when="is_editable",
        ),
        SwitchTo(
            I18NFormat(text_keys.ORDER_CANCEL_BUTTON),
            id="cancel_order",
            state=OrdersStates.CANCEL_CONFIRM,
            when="is_cancellable",
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=OrdersStates.LIST,
        ),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        state=OrdersStates.CARD,
        getter=order_card_getter,
    ),
    Window(
        I18NFormat(text_keys.ORDER_ADDRESS_PROMPT),
        MessageInput(on_address_typed, content_types=[ContentType.TEXT]),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=OrdersStates.CARD,
        ),
        state=OrdersStates.EDIT_ADDRESS,
    ),
    Window(
        I18NFormat(
            text_keys.ORDER_REPEAT_CONFIRM,
            number=Format("{number}"),
            has_cart=Format("{has_cart}"),
            cart_lines=Format("{cart_lines}"),
        ),
        Button(
            I18NFormat(text_keys.ORDER_REPEAT_BUTTON),
            id="repeat_yes",
            on_click=on_repeat_confirmed,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=OrdersStates.CARD,
        ),
        state=OrdersStates.REPEAT_CONFIRM,
        getter=repeat_confirm_getter,
    ),
    Window(
        I18NFormat(
            text_keys.ORDER_REPEAT_PARTIAL,
            when="moved_some",
            moved=Format("{moved}"),
            skipped=Format("{skipped}"),
        ),
        I18NFormat(text_keys.ORDER_REPEAT_NOTHING, when="moved_nothing"),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=OrdersStates.CARD,
        ),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        state=OrdersStates.REPEAT_RESULT,
        getter=repeat_result_getter,
    ),
    Window(
        I18NFormat(text_keys.ORDER_CANCEL_CONFIRM, number=Format("{number}")),
        Button(
            I18NFormat(text_keys.ORDER_CANCEL_YES_BUTTON),
            id="cancel_yes",
            on_click=on_cancel_confirmed,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=OrdersStates.CARD,
        ),
        state=OrdersStates.CANCEL_CONFIRM,
        getter=order_card_getter,
    ),
    on_start=on_dialog_start,
)
"""The customer's order history.

The confirmation-free screen is deliberate and so are the two confirmations.
Retyping an address is reversible — retype it again — so it costs a tap and no
question. Cancelling is not: ``CANCELLED`` has no transitions out of it, and an
order taken back by a stray tap has to be placed a second time from an empty
cart.

The repeat asks too, for a smaller reason than cancellation and a real one: it
writes into a cart the person may have been assembling, and the confirmation is
the one place that can say what will happen to what is already in there. It is
offered on every order, finished ones included — buying the same thing again is
what the button is for, and a completed order is the likeliest thing to repeat.

The cancellation screen shares the card's getter rather than caching the
number, so it can only ever name the order the card was showing. The repeat
screens cannot share it: one of them needs the cart as well, and the other
reports what a command did rather than what anything currently holds.
"""
