import operator
from typing import Final

from aiogram import F
from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, SwitchTo
from aiogram_dialog.widgets.text import Format

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.admin.callbacks import (
    on_blocked,
    on_close,
    on_next_page,
    on_previous_page,
    on_role_selected,
    on_unblocked,
    on_user_selected,
)
from goldy.presentation.telegram.handlers.admin.getters import (
    roles_getter,
    user_card_getter,
    users_getter,
)
from goldy.presentation.telegram.handlers.admin.states import AdminStates

ADMIN_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(
            text_keys.ADMIN_USERS_TITLE,
            page=Format("{page}"),
            pages=Format("{pages}"),
            total=Format("{total}"),
        ),
        I18NFormat(text_keys.ADMIN_EMPTY, when="is_empty"),
        Group(
            Select(
                Format("{item[0]}"),
                id="user_select",
                item_id_getter=operator.itemgetter(1),
                items="users",
                on_click=on_user_selected,
            ),
            width=1,
        ),
        Row(
            Button(
                I18NFormat(text_keys.ADMIN_PREV_BUTTON),
                id="prev",
                on_click=on_previous_page,
                when="has_prev",
            ),
            Button(
                I18NFormat(text_keys.ADMIN_NEXT_BUTTON),
                id="next",
                on_click=on_next_page,
                when="has_next",
            ),
        ),
        Button(I18NFormat(text_keys.ADMIN_CLOSE_BUTTON), id="close", on_click=on_close),
        state=AdminStates.USERS,
        getter=users_getter,
    ),
    Window(
        I18NFormat(
            text_keys.ADMIN_USER_CARD,
            name=Format("{name}"),
            phone=Format("{phone}"),
            role=Format("{role}"),
            status=Format("{status}"),
            locale=Format("{locale}"),
            reason=Format("{reason}"),
        ),
        SwitchTo(
            I18NFormat(text_keys.ADMIN_BLOCK_BUTTON),
            id="block",
            state=AdminStates.BLOCK_REASON,
            when=~F["is_blocked"],
        ),
        Button(
            I18NFormat(text_keys.ADMIN_UNBLOCK_BUTTON),
            id="unblock",
            on_click=on_unblocked,
            when="is_blocked",
        ),
        SwitchTo(
            I18NFormat(text_keys.ADMIN_ROLE_BUTTON),
            id="role",
            state=AdminStates.ROLE,
        ),
        SwitchTo(
            I18NFormat(text_keys.ADMIN_BACK_BUTTON),
            id="back",
            state=AdminStates.USERS,
        ),
        state=AdminStates.CARD,
        getter=user_card_getter,
    ),
    Window(
        I18NFormat(text_keys.ADMIN_BLOCK_REASON_PROMPT),
        MessageInput(on_blocked, content_types=[ContentType.TEXT]),
        SwitchTo(
            I18NFormat(text_keys.ADMIN_BACK_BUTTON),
            id="back",
            state=AdminStates.CARD,
        ),
        state=AdminStates.BLOCK_REASON,
    ),
    Window(
        I18NFormat(text_keys.ADMIN_ROLE_PROMPT),
        Group(
            Select(
                Format("{item[0]}"),
                id="role_select",
                item_id_getter=operator.itemgetter(1),
                items="roles",
                on_click=on_role_selected,
            ),
            width=2,
        ),
        SwitchTo(
            I18NFormat(text_keys.ADMIN_BACK_BUTTON),
            id="back",
            state=AdminStates.CARD,
        ),
        state=AdminStates.ROLE,
        getter=roles_getter,
    ),
)
