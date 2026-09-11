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
from goldy.presentation.telegram.handlers.manage_orders.callbacks import (
    on_cancellation_reason_typed,
    on_close,
    on_filter_cleared,
    on_filter_selected,
    on_order_selected,
    on_status_selected,
)
from goldy.presentation.telegram.handlers.manage_orders.getters import (
    filters_getter,
    managed_order_card_getter,
    queue_getter,
    transitions_getter,
)
from goldy.presentation.telegram.handlers.manage_orders.states import ManageOrdersStates

MANAGE_ORDERS_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(
            text_keys.MANAGE_ORDERS_TITLE,
            page=Format("{page}"),
            pages=Format("{pages}"),
            total=Format("{total}"),
        ),
        I18NFormat(text_keys.MANAGE_ORDERS_EMPTY, when="is_empty"),
        Group(
            Select(
                Format("{item[0]}"),
                id="queue_select",
                item_id_getter=operator.itemgetter(1),
                items="orders",
                on_click=on_order_selected,
            ),
            width=1,
        ),
        paging_row(),
        SwitchTo(
            I18NFormat(text_keys.MANAGE_ORDERS_FILTER_BUTTON, filter=Format("{filter}")),
            id="filter",
            state=ManageOrdersStates.FILTER,
        ),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        state=ManageOrdersStates.QUEUE,
        getter=queue_getter,
    ),
    Window(
        I18NFormat(text_keys.MANAGE_ORDERS_FILTER_PROMPT),
        Group(
            Select(
                Format("{item[0]}"),
                id="filter_select",
                item_id_getter=operator.itemgetter(1),
                items="statuses",
                on_click=on_filter_selected,
            ),
            width=2,
        ),
        Button(
            I18NFormat(text_keys.MANAGE_ORDERS_FILTER_ANY_BUTTON),
            id="filter_any",
            on_click=on_filter_cleared,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=ManageOrdersStates.QUEUE,
        ),
        state=ManageOrdersStates.FILTER,
        getter=filters_getter,
    ),
    Window(
        I18NFormat(
            text_keys.MANAGE_ORDERS_CARD,
            number=Format("{number}"),
            date=Format("{date}"),
            status=Format("{status}"),
            customer=Format("{customer}"),
            blocked_mark=Format("{blocked_mark}"),
            address=Format("{address}"),
            recipient=Format("{recipient}"),
            phone=Format("{phone}"),
            has_comment=Format("{has_comment}"),
            comment=Format("{comment}"),
            lines=Format("{lines}"),
            total=Format("{total}"),
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
            I18NFormat(text_keys.MANAGE_ORDERS_STATUS_BUTTON),
            id="status",
            state=ManageOrdersStates.STATUS,
            when="is_open",
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=ManageOrdersStates.QUEUE,
        ),
        Button(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close", on_click=on_close),
        state=ManageOrdersStates.CARD,
        getter=managed_order_card_getter,
    ),
    Window(
        I18NFormat(text_keys.MANAGE_ORDERS_STATUS_PROMPT),
        Group(
            Select(
                Format("{item[0]}"),
                id="status_select",
                item_id_getter=operator.itemgetter(1),
                items="statuses",
                on_click=on_status_selected,
            ),
            width=2,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=ManageOrdersStates.CARD,
        ),
        state=ManageOrdersStates.STATUS,
        getter=transitions_getter,
    ),
    Window(
        I18NFormat(text_keys.MANAGE_ORDERS_REASON_PROMPT),
        MessageInput(on_cancellation_reason_typed, content_types=[ContentType.TEXT]),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back",
            state=ManageOrdersStates.CARD,
        ),
        state=ManageOrdersStates.CANCEL_REASON,
    ),
)
"""The staff order queue.

The card carries no "next steps" line, and that is not an oversight. What that
message promises — a manager will call you — is a promise made to the buyer by
the person reading this screen; printing it back at them would be the shop
reassuring itself.

"Change status" disappears on a finished order rather than opening an empty
picker, because ``COMPLETED`` and ``CANCELLED`` have no transitions out of them
and a screen offering nothing is a screen that looks broken.
"""
