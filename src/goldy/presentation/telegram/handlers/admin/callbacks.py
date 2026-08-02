import logging
from typing import Any, Final

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.users.block_user.command import BlockUserCommand
from goldy.application.commands.users.change_user_role.command import (
    ChangeUserRoleCommand,
)
from goldy.application.commands.users.unblock_user.command import UnblockUserCommand
from goldy.application.common.mediator.sender import Sender
from goldy.domain.users.values.user_role import UserRole
from goldy.presentation.telegram.handlers.admin.getters import (
    PAGE_KEY,
    USER_ID_KEY,
    current_page,
    selected_user_id,
)
from goldy.presentation.telegram.handlers.admin.states import AdminStates

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def on_user_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data[USER_ID_KEY] = item_id
    await manager.switch_to(AdminStates.CARD)


async def on_previous_page(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    manager.dialog_data[PAGE_KEY] = max(0, current_page(manager) - 1)


async def on_next_page(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    manager.dialog_data[PAGE_KEY] = current_page(manager) + 1


@inject
async def on_blocked(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Blocks the selected person, with the typed reason on the record.

    Whether this administrator is allowed to block *this* person is not checked
    here. ``CanManageSubordinate`` decides it inside the handler, and a refusal
    comes back as an authorization error the central handler renders — which
    also means an administrator cannot block a peer by reaching this screen.
    """
    await sender.send(
        BlockUserCommand(
            user_id=selected_user_id(manager),
            reason=(message.text or "").strip(),
        ),
    )
    await manager.switch_to(AdminStates.CARD)


@inject
async def on_unblocked(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    await sender.send(UnblockUserCommand(user_id=selected_user_id(manager)))
    await manager.switch_to(AdminStates.CARD)


@inject
async def on_role_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
    sender: FromDishka[Sender],
) -> None:
    await sender.send(
        ChangeUserRoleCommand(
            user_id=selected_user_id(manager),
            role=UserRole(item_id),
        ),
    )
    await manager.switch_to(AdminStates.CARD)


async def on_close(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    await manager.done()
