import logging
from typing import Any, Final

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.users.change_notification_preferences.command import (
    ChangeNotificationPreferencesCommand,
)
from goldy.application.commands.users.change_user_locale.command import (
    ChangeUserLocaleCommand,
)
from goldy.application.commands.users.rename_user.command import RenameUserCommand
from goldy.application.commands.users.unlink_messenger_account.command import (
    UnlinkMessengerAccountCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.user import UserView
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.presentation.telegram.handlers.profile.states import ProfileStates
from goldy.presentation.telegram.middlewares.auth_middleware import USER_KEY

logger: Final[logging.Logger] = logging.getLogger(__name__)


@inject
async def on_rename(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Renames the person to whatever they typed.

    A blank surname is normal — the first word is the name, the rest is the
    surname, and one word means no surname rather than an error. Anything the
    domain does refuse comes back as a domain error, which the central error
    handler turns into a message.
    """
    user: UserView = manager.middleware_data[USER_KEY]
    typed = (message.text or "").strip()
    first_name, _, last_name = typed.partition(" ")

    await sender.send(
        RenameUserCommand(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name.strip() or None,
        ),
    )

    await manager.switch_to(ProfileStates.MAIN)


@inject
async def on_locale_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
    sender: FromDishka[Sender],
) -> None:
    user: UserView = manager.middleware_data[USER_KEY]

    await sender.send(
        ChangeUserLocaleCommand(user_id=user.id, locale=item_id),
    )
    await manager.switch_to(ProfileStates.MAIN)


@inject
async def on_notify_via_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
    sender: FromDishka[Sender],
) -> None:
    user: UserView = manager.middleware_data[USER_KEY]

    await sender.send(
        ChangeNotificationPreferencesCommand(
            user_id=user.id,
            notify_via=MessengerPlatform(item_id),
            marketing_consent=user.marketing_consent,
        ),
    )
    await manager.switch_to(ProfileStates.MAIN)


@inject
async def on_marketing_toggled(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    user: UserView = manager.middleware_data[USER_KEY]

    await sender.send(
        ChangeNotificationPreferencesCommand(
            user_id=user.id,
            notify_via=MessengerPlatform(user.notify_via),
            marketing_consent=not user.marketing_consent,
        ),
    )
    await manager.switch_to(ProfileStates.MAIN)


@inject
async def on_account_unlinked(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
    sender: FromDishka[Sender],
) -> None:
    """Detaches a platform.

    Nothing here checks that it is not the last one — the aggregate does, and
    its refusal reaches the person through the error handler. Repeating the
    rule here would give it two homes and one of them would drift.
    """
    user: UserView = manager.middleware_data[USER_KEY]

    await sender.send(
        UnlinkMessengerAccountCommand(
            user_id=user.id,
            platform=MessengerPlatform(item_id),
        ),
    )
    await manager.switch_to(ProfileStates.MAIN)


async def on_close(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    await manager.done()
