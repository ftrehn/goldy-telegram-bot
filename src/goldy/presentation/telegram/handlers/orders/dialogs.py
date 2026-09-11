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
)
from goldy.presentation.telegram.handlers.orders.getters import (
    order_card_getter,
    orders_getter,
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

The two confirmation-free screens are deliberate and the one confirmation is
too. Retyping an address is reversible — retype it again — so it costs a tap
and no question. Cancelling is not: ``CANCELLED`` has no transitions out of it,
and an order taken back by a mis-tap has to be placed a second time from an
empty cart.

The cancellation screen shares the card's getter rather than caching the
number, so it can only ever name the order the card was showing.
"""
