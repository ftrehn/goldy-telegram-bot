import operator
from typing import Final

from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Group, Select, SwitchTo
from aiogram_dialog.widgets.text import Format

from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.profile.callbacks import (
    on_account_unlinked,
    on_close,
    on_locale_selected,
    on_marketing_toggled,
    on_notify_via_selected,
    on_rename,
)
from goldy.presentation.telegram.handlers.profile.getters import (
    accounts_getter,
    locales_getter,
    profile_getter,
)
from goldy.presentation.telegram.handlers.profile.states import ProfileStates

PROFILE_DIALOG: Final[Dialog] = Dialog(
    Window(
        I18NFormat(
            text_keys.ME_PROFILE,
            name=Format("{name}"),
            phone=Format("{phone}"),
            role=Format("{role}"),
            locale=Format("{locale}"),
            notify=Format("{notify}"),
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_RENAME_BUTTON),
            id="rename",
            state=ProfileStates.RENAME,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_LOCALE_BUTTON),
            id="locale",
            state=ProfileStates.LOCALE,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_NOTIFICATIONS_BUTTON),
            id="notifications",
            state=ProfileStates.NOTIFICATIONS,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_ACCOUNTS_BUTTON),
            id="accounts",
            state=ProfileStates.ACCOUNTS,
            when="can_unlink",
        ),
        Button(I18NFormat(text_keys.PROFILE_CLOSE_BUTTON), id="close", on_click=on_close),
        state=ProfileStates.MAIN,
        getter=profile_getter,
    ),
    Window(
        I18NFormat(text_keys.PROFILE_RENAME_PROMPT),
        MessageInput(on_rename, content_types=[ContentType.TEXT]),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_BACK_BUTTON),
            id="back",
            state=ProfileStates.MAIN,
        ),
        state=ProfileStates.RENAME,
    ),
    Window(
        I18NFormat(text_keys.PROFILE_LOCALE_PROMPT),
        Group(
            Select(
                Format("{item[0]}"),
                id="locale_select",
                item_id_getter=operator.itemgetter(1),
                items="locales",
                on_click=on_locale_selected,
            ),
            width=2,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_BACK_BUTTON),
            id="back",
            state=ProfileStates.MAIN,
        ),
        state=ProfileStates.LOCALE,
        getter=locales_getter,
    ),
    Window(
        I18NFormat(text_keys.PROFILE_NOTIFICATIONS_PROMPT, notify=Format("{notify}")),
        Group(
            Select(
                Format("{item[0]}"),
                id="notify_select",
                item_id_getter=operator.itemgetter(1),
                items="accounts",
                on_click=on_notify_via_selected,
            ),
            width=2,
        ),
        Button(
            I18NFormat(text_keys.PROFILE_MARKETING_BUTTON),
            id="marketing",
            on_click=on_marketing_toggled,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_BACK_BUTTON),
            id="back",
            state=ProfileStates.MAIN,
        ),
        state=ProfileStates.NOTIFICATIONS,
        getter=accounts_getter,
    ),
    Window(
        I18NFormat(text_keys.PROFILE_ACCOUNTS_PROMPT),
        Group(
            Select(
                Format("{item[0]}"),
                id="unlink_select",
                item_id_getter=operator.itemgetter(1),
                items="accounts",
                on_click=on_account_unlinked,
            ),
            width=2,
        ),
        SwitchTo(
            I18NFormat(text_keys.PROFILE_BACK_BUTTON),
            id="back",
            state=ProfileStates.MAIN,
        ),
        state=ProfileStates.ACCOUNTS,
        getter=accounts_getter,
    ),
)
