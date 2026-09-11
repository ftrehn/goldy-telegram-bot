from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.change_delivery_address.command import (
    ChangeDeliveryAddressCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.widgets import I18N_CONTEXT_KEY
from goldy.presentation.telegram.handlers.orders.getters import (
    ORDER_ID_KEY,
    selected_order_id,
)
from goldy.presentation.telegram.handlers.orders.states import OrdersStates


async def on_dialog_start(start_data: object, manager: DialogManager) -> None:
    """Opens on a card when somebody handed us an order to show.

    Checkout ends on a screen offering to open the order it has just placed,
    and it does that by starting this dialog at ``CARD`` with the identifier in
    its start data. The card screens read that identifier out of
    ``dialog_data``, so it has to be there before the first render.

    Started by ``/orders`` there is no start data at all, and the list opens as
    usual. Anything else that arrives is ignored rather than trusted: start
    data is whatever the caller put there, and a card built from a malformed
    one would fail at render time instead of at the mistake.
    """
    if not isinstance(start_data, dict):
        return

    order_id = start_data.get(ORDER_ID_KEY)

    if isinstance(order_id, str):
        manager.dialog_data[ORDER_ID_KEY] = order_id


async def on_order_selected(
    _callback: CallbackQuery,
    _widget: Select[Any],
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data[ORDER_ID_KEY] = item_id
    await manager.switch_to(OrdersStates.CARD)


@inject
async def on_address_typed(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Sends an already placed order somewhere else.

    Whether the order may still be edited is not checked here. The button is
    drawn only while the read model says it is, and the aggregate refuses
    anything later with ``OrderNotEditableError`` — which reaches the person
    through the central error handler. A third statement of the rule in this
    callback would be the one that drifts.
    """
    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]

    await sender.send(
        ChangeDeliveryAddressCommand(
            order_id=selected_order_id(manager),
            delivery_address=(message.text or "").strip(),
        ),
    )

    await message.answer(i18n.get(text_keys.ORDER_ADDRESS_CHANGED_TOAST))
    await manager.switch_to(OrdersStates.CARD)


@inject
async def on_cancel_confirmed(
    callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
    sender: FromDishka[Sender],
) -> None:
    """Takes the order back, on the second tap rather than the first.

    The confirmation screen exists because this cannot be undone: there is no
    way back out of ``CANCELLED`` in the transition table, and a buyer who
    meant to open the card would otherwise lose the order to a stray tap.

    No reason is asked for. Somebody withdrawing their own order owes nobody an
    explanation, and the asymmetry with a manager cancelling somebody else's is
    held by the aggregate rather than restated here.
    """
    i18n: I18nContext = manager.middleware_data[I18N_CONTEXT_KEY]

    await sender.send(CancelOrderCommand(order_id=selected_order_id(manager)))

    await callback.answer(i18n.get(text_keys.ORDER_CANCELLED_TOAST))
    await manager.switch_to(OrdersStates.CARD)


async def on_close(
    _callback: CallbackQuery,
    _widget: Button,
    manager: DialogManager,
) -> None:
    await manager.done()
