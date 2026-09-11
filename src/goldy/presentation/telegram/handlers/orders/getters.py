from typing import Any, Final
from uuid import UUID

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.order import OrderListItemView
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    format_money,
    format_order_date,
    format_order_number,
    format_order_status,
)
from goldy.presentation.telegram.common.order_cards import (
    fit_lines,
    format_order_lines,
    lines_budget,
    order_card_data,
)
from goldy.presentation.telegram.common.paging import page_request, paging_data

ORDER_ID_KEY: Final[str] = "order_id"
"""Which order the card screens are about, as text.

``dialog_data`` is serialised into storage between updates, so a ``UUID`` kept
there would not survive the round trip. It is parsed back at the one place that
needs it rather than at every reader.
"""


def selected_order_id(manager: DialogManager) -> UUID:
    order_id: str = manager.dialog_data[ORDER_ID_KEY]

    return UUID(order_id)


@inject
async def orders_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of this person's orders, newest first.

    Whose orders these are is not a parameter and cannot be made into one:
    ``ListMyOrdersQuery`` carries no customer field and takes the identifier
    from the identity provider, so there is physically nothing here to point at
    somebody else's history.

    Finished orders are in the page. "Where is the order I placed last spring"
    is an ordinary question, and a history that quietly drops what it considers
    over cannot answer it.
    """
    limit, offset = page_request(dialog_manager)
    view = await sender.send(ListMyOrdersQuery(limit=limit, offset=offset))

    return {
        "orders": [(_row(i18n, order), str(order.id)) for order in view.orders],
        "is_empty": not view.orders,
        **paging_data(dialog_manager, total=view.total),
    }


@inject
async def order_card_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The selected order, re-read on every render.

    Re-reading is what makes a cancellation or a corrected address show up the
    moment the dialog comes back to this screen, without anybody having to
    invalidate a copy held in ``dialog_data``. It is also what keeps the
    buttons honest: ``is_cancellable`` and ``is_editable`` are computed by the
    read model from the same tables the aggregate will refuse by.

    The same getter feeds the cancellation confirmation, which needs the
    number, so that screen cannot name an order the card is no longer showing.

    The lines are cut to what the card has room for, which is a Fluent ceiling
    before it is a Telegram one: a placeable over 2500 characters fails the
    whole message instead of being shortened, and an order of nine positions
    with names the length 1C allows already passes it. Built in two passes for
    that reason — the card is rendered empty to find out how much room the
    address and the comment have left.
    """
    order = await sender.send(GetOrderQuery(order_id=selected_order_id(dialog_manager)))
    card = order_card_data(i18n, order, lines="")
    budget = lines_budget(i18n, text_keys.ORDER_CARD, card)

    return {
        **card,
        "lines": fit_lines(
            i18n,
            format_order_lines(i18n, order.lines),
            budget=budget,
        ),
    }


def _row(i18n: I18nContext, order: OrderListItemView) -> str:
    """One line of the history, worded to fit on a button."""
    return i18n.get(
        text_keys.ORDERS_LIST_ITEM,
        number=format_order_number(i18n, order.number),
        date=format_order_date(order.created_at, i18n.locale),
        total=format_money(order.total, i18n.locale),
        status=format_order_status(i18n, order.status),
    )
