from collections.abc import Sequence
from typing import Any, Final
from uuid import UUID

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.order import OrderListItemView, OrderView
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    flag,
    for_message_text,
    format_money,
    format_order_date,
    format_order_number,
    format_order_status,
)
from goldy.presentation.telegram.common.order_cards import (
    LINE_SEPARATOR,
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


REPEAT_MOVED_KEY: Final[str] = "repeat_moved"
"""How many positions of the order reached the cart, written by the callback.

The result screen is drawn after the command has run and the command is the
only thing that knows this, so the number is left behind for the render that
follows it — the same trick the cart's line screen plays with the quantity it
drew.
"""

REPEAT_SKIPPED_KEY: Final[str] = "repeat_skipped"
"""The names of what could not be carried over, as a plain list of strings.

``dialog_data`` is serialised between updates, which rules out anything richer.
Names rather than product identifiers because a product the import dropped has
no row left to look a name up in: the order line it was snapshotted into is the
last place one survives.
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


def repeat_confirm_data(
    i18n: I18nContext,
    order: OrderView,
    cart_line_count: int,
) -> dict[str, Any]:
    """What the confirmation screen says, from an order and a cart size.

    Takes the size rather than the whole cart, because that is the only thing
    this screen has to say about it: the repeat merges into the cart instead of
    emptying it, and somebody halfway through assembling one has to be told
    that before they press the button rather than after.

    Split out of the getter so that the wording can be rendered in a test
    against the real ``.ftl`` files without a dialog manager, the way
    ``order_card_data`` is.
    """
    return {
        "number": format_order_number(i18n, order.number),
        "cart_lines": cart_line_count,
        "has_cart": flag(value=cart_line_count > 0),
    }


def repeat_result_data(
    i18n: I18nContext,
    moved: int,
    skipped: Sequence[str],
) -> dict[str, Any]:
    """What the outcome screen says: a count, and the names that did not fit.

    The names are cut to the room the message has for the reason an order card
    is: Fluent refuses a single placeable over ``MAX_PLACEABLE_LENGTH`` by
    failing the whole message rather than by shortening it, and a wholesale
    order of a hundred positions whose products have all been withdrawn reaches
    that ceiling easily. ``fit_lines`` keeps whole names and says how many it
    left out, which is the same promise the card makes.

    Every name goes through ``for_message_text``: these come out of 1C by way of
    a snapshot, and a product called ``Уголок <60>`` would otherwise close the
    bold tag the message opened.
    """
    budget = lines_budget(
        i18n,
        text_keys.ORDER_REPEAT_PARTIAL,
        {"moved": str(moved), "skipped": ""},
    )
    names = LINE_SEPARATOR.join(for_message_text(name) for name in skipped)

    return {
        "moved": moved,
        "skipped": fit_lines(i18n, names, budget=budget),
        "moved_some": moved > 0,
        "moved_nothing": moved == 0,
    }


@inject
async def repeat_confirm_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The order about to be repeated, and how full the cart already is.

    Two reads rather than one, and the second is the reason this screen exists
    at all: a repeat into an empty cart needs no explanation, while a repeat
    into a cart with eight positions in it is a promise about what happens to
    those eight.

    Both are re-read on every render, so the count on the screen is never older
    than the keyboard under it.
    """
    order = await sender.send(GetOrderQuery(order_id=selected_order_id(dialog_manager)))
    cart = await sender.send(GetCartQuery())

    return repeat_confirm_data(i18n, order, cart.line_count)


async def repeat_result_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    **_kwargs: Any,
) -> dict[str, Any]:
    """The outcome of the repeat, read back off what the callback left behind.

    Nothing is re-read here, and that is deliberate: this screen reports one
    past event rather than the current state of anything. Asking the cart again
    would answer with a number that has since moved — the person may have
    opened the cart in another chat — and a report that changes while it is
    being read is not a report.
    """
    skipped: list[str] = dialog_manager.dialog_data[REPEAT_SKIPPED_KEY]

    return repeat_result_data(
        i18n,
        dialog_manager.dialog_data[REPEAT_MOVED_KEY],
        skipped,
    )


def _row(i18n: I18nContext, order: OrderListItemView) -> str:
    """One line of the history, worded to fit on a button."""
    return i18n.get(
        text_keys.ORDERS_LIST_ITEM,
        number=format_order_number(i18n, order.number),
        date=format_order_date(order.created_at, i18n.locale),
        total=format_money(order.total, i18n.locale),
        status=format_order_status(i18n, order.status),
    )
