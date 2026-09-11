from typing import Any, Final
from uuid import UUID

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.order import OrderListItemView
from goldy.application.common.views.user import UserView
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.application.queries.users.get_user_by_id.query import GetUserByIdQuery
from goldy.domain.orders.status_transitions import ALLOWED_ORDER_TRANSITIONS
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    for_message_text,
    format_money,
    format_order_date,
    format_order_number,
    format_order_status,
)
from goldy.presentation.telegram.common.order_cards import (
    fit_lines,
    format_queue_lines,
    lines_budget,
    order_card_data,
)
from goldy.presentation.telegram.common.paging import page_request, paging_data

ORDER_ID_KEY: Final[str] = "order_id"

STATUS_FILTER_KEY: Final[str] = "status_filter"
"""Which status the queue is narrowed to, or absent for all of them.

Absent by default on purpose. ``OrderFilters`` already states that hiding
finished orders is a behaviour nobody asked for and that filtering is a button
somebody presses; a queue opening pre-filtered would be presentation
re-deciding that, and a manager looking for an order they shipped yesterday
would conclude it had vanished.
"""


def selected_order_id(manager: DialogManager) -> UUID:
    order_id: str = manager.dialog_data[ORDER_ID_KEY]

    return UUID(order_id)


def selected_filter(manager: DialogManager) -> OrderStatus | None:
    """The status the queue is narrowed to, if any."""
    status: str | None = manager.dialog_data.get(STATUS_FILTER_KEY)

    if status is None:
        return None

    return OrderStatus(status)


@inject
async def queue_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of every customer's orders, newest first.

    A different query from the customer's history rather than the same one with
    a customer filter, and the difference is a security boundary: this one is
    guarded by ``IsStaff`` inside the handler, while the other takes the
    customer from the identity provider and cannot be pointed at a stranger at
    all. The router's staff filter is not what keeps a buyer out of here — it
    only keeps them from learning that the command exists.
    """
    limit, offset = page_request(dialog_manager)
    status = selected_filter(dialog_manager)
    view = await sender.send(
        ListOrdersQuery(limit=limit, offset=offset, status=status),
    )

    return {
        "orders": [(_row(i18n, order), str(order.id)) for order in view.orders],
        "is_empty": not view.orders,
        "filter": _filter_label(i18n, status),
        **paging_data(dialog_manager, total=view.total),
    }


@inject
async def managed_order_card_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The selected order as staff see it: lines with stock, and who ordered.

    Two reads rather than one, because ``OrderView`` carries the customer's
    identifier and not their name — it is the buyer's own card as much as the
    manager's, and a buyer does not need to be told who they are. The name
    comes from ``GetUserByIdQuery``, a lookup by primary key guarded by
    ``IsStaff`` on its own, so the second read is no wider a door than the
    first.

    The blocked mark is taken off the order view rather than off that user:
    both come from the same row, and it is the order view that documents the
    fact as something for the manager to weigh. Blocking is about access, not
    about obligations — an order placed before one can perfectly well go on to
    be confirmed, so this screen warns and the person decides.

    The queue line carries a stock figure the buyer's does not, so this card
    runs out of room sooner than theirs — and running out is not a truncated
    card but no card at all, because Fluent fails a message whose placeable
    grows past 2500 characters. The lines are therefore measured against what
    this card has left after the customer, the address and the comment, and cut
    with a count of what did not fit.
    """
    order = await sender.send(GetOrderQuery(order_id=selected_order_id(dialog_manager)))
    customer = await sender.send(GetUserByIdQuery(user_id=order.customer_id))

    card = {
        **order_card_data(i18n, order, lines=""),
        "customer": customer_label(customer),
        "blocked_mark": (
            i18n.get(text_keys.MANAGE_ORDERS_CUSTOMER_BLOCKED)
            if order.customer_is_blocked
            else ""
        ),
    }
    budget = lines_budget(i18n, text_keys.MANAGE_ORDERS_CARD, card)

    return {
        **card,
        "lines": fit_lines(
            i18n,
            format_queue_lines(i18n, order.lines),
            budget=budget,
        ),
    }


async def filters_getter(i18n: I18nContext, **_kwargs: Any) -> dict[str, Any]:
    """Every status the queue can be narrowed to.

    All of them, in lifecycle order, the two an order never leaves included: a
    manager looking for what was cancelled last week is asking an ordinary
    question, and a filter that cannot express it sends them to the database.
    """
    return {
        "statuses": [
            (format_order_status(i18n, status.value), status.value)
            for status in OrderStatus
        ],
    }


@inject
async def transitions_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The moves this order may actually make, read out of the lifecycle table.

    Only the legal ones rather than all five, for the reason the admin role
    picker leaves ``ADMIN`` out: a button certain to come back refused is worse
    than no button. ``ALLOWED_ORDER_TRANSITIONS`` is the one place that knows,
    and the aggregate still refuses independently — this is the same table read
    twice, not the rule stated twice.

    The buttons come out in the enum's own order, which is the order of the
    lifecycle, so moving the order along is the first button and stopping it is
    the last. Sorting them any other way would put "cancelled" first.
    """
    order = await sender.send(GetOrderQuery(order_id=selected_order_id(dialog_manager)))
    allowed = ALLOWED_ORDER_TRANSITIONS[OrderStatus(order.status)]

    return {
        "statuses": [
            (format_order_status(i18n, status.value), status.value)
            for status in OrderStatus
            if status in allowed
        ],
    }


def _row(i18n: I18nContext, order: OrderListItemView) -> str:
    """One line of the queue, worded to fit on a button."""
    return i18n.get(
        text_keys.MANAGE_ORDERS_ITEM,
        number=format_order_number(i18n, order.number),
        date=format_order_date(order.created_at, i18n.locale),
        customer=order.customer_name or "",
        total=format_money(order.total, i18n.locale),
        status=format_order_status(i18n, order.status),
    )


def _filter_label(i18n: I18nContext, status: OrderStatus | None) -> str:
    """What the filter button says it is currently showing."""
    if status is None:
        return i18n.get(text_keys.MANAGE_ORDERS_FILTER_ANY)

    return format_order_status(i18n, status.value)


def customer_label(customer: UserView) -> str:
    """Who placed the order, with the number to reach them on.

    The recipient's phone is already on the card and is often somebody else's —
    a present sent to a relative, a delivery to an office. When the order
    itself needs discussing, the buyer is who to call.

    Quoted here rather than at the card, because the card is the only thing
    this line is for: it goes into message text and never onto a button, so
    there is one answer to the question :func:`for_message_text` asks and it
    belongs with the name it is about. A customer registered from Telegram
    under ``<Вася>`` would otherwise make their every order unopenable for the
    manager who has to pick it.
    """
    name = (
        customer.first_name
        if customer.last_name is None
        else f"{customer.first_name} {customer.last_name}"
    )

    return for_message_text(f"{name} · {customer.phone_number}")
