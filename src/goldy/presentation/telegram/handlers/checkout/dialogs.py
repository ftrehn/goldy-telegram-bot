from typing import Final

from aiogram import F
from aiogram.enums import ContentType
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Start, SwitchTo
from aiogram_dialog.widgets.text import Format

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.catalog.states import CatalogStates
from goldy.presentation.telegram.handlers.checkout.callbacks import (
    on_address_typed,
    on_comment_skipped,
    on_comment_typed,
    on_confirmed,
    on_last_address_chosen,
    on_open_order,
    on_own_phone_chosen,
    on_phone_typed,
    on_recipient_is_me,
    on_recipient_typed,
)
from goldy.presentation.telegram.handlers.checkout.getters import (
    address_getter,
    confirm_getter,
    done_getter,
    phone_getter,
)
from goldy.presentation.telegram.handlers.checkout.states import CheckoutStates

CHECKOUT_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(text_keys.CHECKOUT_ADDRESS_PROMPT),
        MessageInput(on_address_typed, content_types=[ContentType.TEXT]),
        Button(
            I18NFormat(
                text_keys.CHECKOUT_ADDRESS_LAST_BUTTON,
                address=Format("{last_address}"),
            ),
            id="last_address",
            on_click=on_last_address_chosen,
            when="has_last_address",
        ),
        Cancel(I18NFormat(text_keys.COMMON_CANCEL_BUTTON), id="cancel_address"),
        state=CheckoutStates.ADDRESS,
        getter=address_getter,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_RECIPIENT_PROMPT),
        MessageInput(on_recipient_typed, content_types=[ContentType.TEXT]),
        Button(
            I18NFormat(text_keys.CHECKOUT_RECIPIENT_ME_BUTTON),
            id="recipient_is_me",
            on_click=on_recipient_is_me,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_address",
            state=CheckoutStates.ADDRESS,
        ),
        state=CheckoutStates.RECIPIENT,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_PHONE_PROMPT),
        MessageInput(on_phone_typed, content_types=[ContentType.TEXT]),
        Button(
            I18NFormat(text_keys.CHECKOUT_PHONE_MINE_BUTTON, phone=Format("{phone}")),
            id="own_phone",
            on_click=on_own_phone_chosen,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_recipient",
            state=CheckoutStates.RECIPIENT,
        ),
        state=CheckoutStates.PHONE,
        getter=phone_getter,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_COMMENT_PROMPT),
        MessageInput(on_comment_typed, content_types=[ContentType.TEXT]),
        Button(
            I18NFormat(text_keys.CHECKOUT_SKIP_BUTTON),
            id="skip_comment",
            on_click=on_comment_skipped,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_phone",
            state=CheckoutStates.PHONE,
        ),
        state=CheckoutStates.COMMENT,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_REPRICED_NOTICE, when="repriced"),
        I18NFormat(
            text_keys.CHECKOUT_CONFIRM,
            address=Format("{address}"),
            recipient=Format("{recipient}"),
            phone=Format("{phone}"),
            has_comment=Format("{has_comment}"),
            comment=Format("{comment}"),
            count=F["count"],
            total=Format("{total}"),
        ),
        Button(
            I18NFormat(text_keys.CHECKOUT_CONFIRM_BUTTON),
            id="confirm",
            on_click=on_confirmed,
        ),
        SwitchTo(
            I18NFormat(text_keys.COMMON_BACK_BUTTON),
            id="back_to_comment",
            state=CheckoutStates.COMMENT,
        ),
        Cancel(I18NFormat(text_keys.COMMON_CANCEL_BUTTON), id="cancel_checkout"),
        state=CheckoutStates.CONFIRM,
        getter=confirm_getter,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_PLACING),
        state=CheckoutStates.PLACING,
    ),
    Window(
        I18NFormat(text_keys.CHECKOUT_ALREADY_PLACED),
        Cancel(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close_already_placed"),
        state=CheckoutStates.ALREADY_PLACED,
    ),
    Window(
        I18NFormat(
            text_keys.CHECKOUT_DONE,
            number=Format("{number}"),
            phone=Format("{phone}"),
        ),
        Button(
            I18NFormat(text_keys.CHECKOUT_OPEN_ORDER_BUTTON),
            id="open_order",
            on_click=on_open_order,
            when="has_order_id",
        ),
        Start(
            I18NFormat(text_keys.CHECKOUT_TO_CATALOG_BUTTON),
            id="done_to_catalog",
            state=CatalogStates.CATEGORIES,
            mode=StartMode.RESET_STACK,
        ),
        Cancel(I18NFormat(text_keys.COMMON_CLOSE_BUTTON), id="close_done"),
        state=CheckoutStates.DONE,
        getter=done_getter,
    ),
)
"""The five screens an order is filled in on, plus the three it ends on.

``PLACING`` carries no keyboard on purpose — it is what the person sees while
the command runs, and its emptiness is the point.

``DONE`` offers the order it has just placed, and then the catalog. The button
that opens it is a plain ``Button`` rather than a ``Start``: a widget's start
data is fixed when the window is built, and the identifier only exists once the
command has answered. The orders dialog fills its ``dialog_data`` from that
start data in its own ``on_start`` hook, which is what makes a card openable
from outside at all.
"""
