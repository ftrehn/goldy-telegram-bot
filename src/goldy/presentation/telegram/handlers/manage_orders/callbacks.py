from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.paging import reset_paging
from goldy.presentation.telegram.common.widgets import I18N_CONTEXT_KEY
from goldy.presentation.telegram.handlers.manage_orders.getters import (
    ORDER_ID_KEY,
    STATUS_FILTER_KEY,
    selected_order_id,
)
from goldy.presentation.telegram.handlers.manage_orders.states import ManageOrdersStates


async def on_order_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data[ORDER_ID_KEY] = item_id
    await manager.switch_to(ManageOrdersStates.CARD)


async def on_filter_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    """Narrows the queue to one status and sends it back to the first page.

    Resetting the pager is not tidiness. Filtering to a status with two orders
    while standing on page four shows an empty screen with a "previous" button,
    which reads as the filter being broken rather than as the page being past
    the end.
    """
    manager.dialog_data[STATUS_FILTER_KEY] = item_id
    reset_paging(manager)
    await manager.switch_to(ManageOrdersStates.QUEUE)


async def on_filter_cleared(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    """Puts every status back in the queue."""
    manager.dialog_data.pop(STATUS_FILTER_KEY, None)
    reset_paging(manager)
    await manager.switch_to(ManageOrdersStates.QUEUE)


@inject
async def on_status_selected(
    callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
    sender: FromDishka[Sender],
) -> None:
    """Moves the order along, or asks why before stopping it.

    Cancelling is the one move that needs something typed: ``Order.cancel``
    refuses a manager without a reason, and the customer reads it. Asking on
    the way there rather than letting the command fail is the difference
    between a screen and an error message.

    Nothing here checks that the move is legal. The picker only offers what
    ``ALLOWED_ORDER_TRANSITIONS`` allows from where the order stands, and the
    aggregate refuses anything else — including a transition that became
    illegal between the render and the tap, which is exactly the case a check
    in this callback would still miss.
    """
    status = OrderStatus(item_id)

    if status is OrderStatus.CANCELLED:
        await manager.switch_to(ManageOrdersStates.CANCEL_REASON)
        return

    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]

    await sender.send(
        ChangeOrderStatusCommand(
            order_id=selected_order_id(manager),
            status=status,
        ),
    )

    await callback.answer(i18n.get(text_keys.MANAGE_ORDERS_STATUS_CHANGED_TOAST))
    await manager.switch_to(ManageOrdersStates.CARD)


@inject
async def on_cancellation_reason_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Stops the order, with the typed reason on the record.

    The target status is written here rather than carried from the previous
    screen in ``dialog_data``. Cancelling is the only move that reaches this
    window — the prompt says so in both languages — so a key holding "which
    status did they pick" would be state that can only ever have one value and
    can therefore only ever be wrong.
    """
    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]

    await sender.send(
        ChangeOrderStatusCommand(
            order_id=selected_order_id(manager),
            status=OrderStatus.CANCELLED,
            reason=(message.text or "").strip(),
        ),
    )

    await message.answer(i18n.get(text_keys.MANAGE_ORDERS_STATUS_CHANGED_TOAST))
    await manager.switch_to(ManageOrdersStates.CARD)


async def on_close(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    await manager.done()
