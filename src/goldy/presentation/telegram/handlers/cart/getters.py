from typing import Any, Final

from aiogram_dialog import DialogManager
from aiogram_i18n import I18nContext
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from goldy.application.common.mediator.sender import Sender
from goldy.application.common.views.cart import CartLineView
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.domain.common.values.quantity import MAX_QUANTITY
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    for_message_text,
    format_money,
    format_price,
    format_quantity,
    format_stock,
)
from goldy.presentation.telegram.common.paging import (
    page_request,
    paging_data,
    reset_paging,
)

PRODUCT_ID_KEY: Final[str] = "product_id"
"""Which position the line screen is about, picked on the main screen."""

LINE_QUANTITY_KEY: Final[str] = "line_quantity"
"""How many the line screen last drew, written by the getter that drew it.

The ``-`` button removes the line when it takes away the last piece, and the
screen that offered it has to go back to the list rather than redraw a position
that no longer exists. Whether this press is the last one is knowable only from
the quantity, and the callback has no window data — so the render leaves the
number it drew behind for the callback that follows it.

Kept honest by the redraw: every button on the line screen re-runs this getter,
so the number is never older than the keyboard the person is looking at.
"""

MAX_LABEL_LENGTH: Final[int] = 32
"""How much of a product name a one-line button shows.

Names out of 1C run to a hundred characters — a size, a steel grade and a
standard after the noun. Telegram wraps a long label over three lines and turns
a list of eight into a wall, so the tail is cut and the full name waits on the
line screen, where there is room for it.
"""

ELLIPSIS: Final[str] = "…"


def selected_product_id(manager: DialogManager) -> str:
    product_id: str = manager.dialog_data[PRODUCT_ID_KEY]

    return product_id


def drawn_quantity(manager: DialogManager) -> int:
    """What the line screen last showed, or nothing if it never drew."""
    quantity: int = manager.dialog_data.get(LINE_QUANTITY_KEY, 0)

    return quantity


@inject
async def cart_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """One page of the cart, re-read and re-priced on every render.

    Never cached in ``dialog_data``. Prices live in the catalog projection and
    move with the imports from 1C, while a cart lives for days — a copy taken
    when the dialog opened would eventually offer a number the shop no longer
    charges, and the customer would be the one to find out.

    Paged in the getter and not in the query, which is the opposite of every
    other list in this bot and is right here for one reason: a cart is bounded
    at a hundred lines by the aggregate, so the whole of it is one small read
    that the totals need anyway. What paging protects is the *message*. A
    wholesale cart of forty positions is some four thousand characters of text
    and forty buttons, and Telegram refuses both — the screen would not come
    out shorter, it would not come out at all.

    The totals and the flags below are computed over the whole cart rather than
    over the page, because "checkout" has to answer for every line and not for
    the eight in view.

    Only the two arrow flags are taken from the pager, and taking the whole of
    what it produces would be a silent defect rather than a convenience: it
    answers with a ``total`` meaning "how many rows there are", and on this
    screen ``total`` is the money. Spread over this dictionary it would put the
    number of lines where the title prints the sum.

    ``can_checkout`` withholds the button on two different faults, and each one
    gets a notice of its own rather than one hedged sentence. A product gone
    from the catalog is marked on its line and can be swept away with the
    button beside the warning; a product still listed but with no price under
    this customer's price type is not marked at all — it prints "price on
    request" where its amount would be, and the total below is short by exactly
    that line. One notice covering both would have named a button that does not
    touch half the lines it was talking about. Offering checkout on either
    fault would promise an order the handler then refuses.
    """
    cart = await sender.send(GetCartQuery())
    limit, offset = _page_of(dialog_manager, cart.line_count)
    paging = paging_data(dialog_manager, total=cart.line_count)

    lines = [
        line_arguments(i18n, position, line)
        for position, line in enumerate(
            cart.lines[offset : offset + limit],
            start=offset + 1,
        )
    ]

    return {
        "lines": lines,
        "count": cart.line_count,
        "total": format_money(cart.total, i18n.locale),
        "is_empty": cart.is_empty,
        "has_unavailable": cart.has_unavailable_lines,
        "has_unpriced": cart.has_unpriced_lines,
        "can_checkout": not cart.is_empty
        and not cart.has_unavailable_lines
        and not cart.has_unpriced_lines,
        "has_prev": paging["has_prev"],
        "has_next": paging["has_next"],
    }


def _page_of(manager: DialogManager, total: int) -> tuple[int, int]:
    """Which slice to draw, never one that has fallen off the end.

    Emptying the last page is ordinary here in a way it is not in a catalog:
    the buttons on this screen remove lines, so the page a person is standing
    on can cease to exist under them. Without the clamp they would be left
    looking at an empty cart screen with a "previous" button on it, which reads
    as the cart having been lost.

    """
    limit, offset = page_request(manager)

    if has_fallen_off(offset=offset, total=total):
        reset_paging(manager)
        limit, offset = page_request(manager)

    return limit, offset


def has_fallen_off(*, offset: int, total: int) -> bool:
    """Whether the page being stood on has stopped existing underneath.

    A pure function rather than a condition inside the getter, because the case
    that matters is the one easiest to exclude by accident. Guarding the reset
    on there still being rows left excludes an *emptied* cart — the one state
    where every page has certainly gone — and leaves the person looking at "your
    cart is empty" with a "previous" button under it, which is exactly what the
    clamp was written to prevent.

    The first page never counts as fallen off. There is nowhere behind it to be
    sent back to, and saying otherwise would rewrite ``dialog_data`` on every
    render of an empty cart.
    """
    return offset > 0 and offset >= total


@inject
async def line_getter(
    dialog_manager: DialogManager,
    i18n: I18nContext,
    sender: FromDishka[Sender],
    **_kwargs: Any,
) -> dict[str, Any]:
    """The one position this screen's buttons act on.

    A line can be gone by the time the screen renders — the same cart is open
    in another chat, or a second tap on ``-`` arrived while the first was still
    being handled. That is reported as text rather than raised: an exception
    here would leave the person looking at a keyboard whose every button fails,
    while ``found`` simply hides the four buttons and leaves "back".
    """
    product_id = selected_product_id(dialog_manager)
    cart = await sender.send(GetCartQuery())

    found = next(
        (
            (position, line)
            for position, line in enumerate(cart.lines, start=1)
            if line.product_id == product_id
        ),
        None,
    )

    if found is None:
        dialog_manager.dialog_data[LINE_QUANTITY_KEY] = 0

        return {"found": False, **_blank_line()}

    position, line = found
    dialog_manager.dialog_data[LINE_QUANTITY_KEY] = line.quantity

    return {"found": True, **line_arguments(i18n, position, line)}


async def quantity_getter(**_kwargs: Any) -> dict[str, Any]:
    """The ceiling the prompt names, taken from the value object that holds it.

    Read from ``Quantity`` rather than written into the message, so raising the
    limit changes the screen and the refusal together instead of leaving the
    prompt promising a number the domain rejects.
    """
    return {"max": MAX_QUANTITY}


def line_arguments(
    i18n: I18nContext, position: int, line: CartLineView
) -> dict[str, Any]:
    """One line as both a text row and a button label.

    Every argument ``cart-line`` takes, plus the two the keyboard reads. A
    missing one would not print as itself: the Fluent core raises on an unknown
    external, so a line message short of an argument is a cart screen that does
    not render at all.

    The name is spelled both ways here, which is the clearest case there is for
    :func:`for_message_text`: the row is parsed as HTML and the label beside it
    is not, so a product named ``Уголок <40x40>`` has to be quoted for one and
    left alone for the other.
    """
    name = line_name(line)

    return {
        "product_id": line.product_id,
        "position": position,
        "name": for_message_text(name),
        "label": line_label(position, name),
        "quantity": format_quantity(line.quantity, line.unit_name),
        "price": format_price(i18n, line.unit_price),
        "total": format_price(i18n, line.line_total),
        "mark": line_mark(i18n, line),
    }


def _blank_line() -> dict[str, Any]:
    """Placeholders for a line that is not there any more.

    Every field the line message takes is present and empty. The message itself
    is hidden by ``found``, so nothing renders these — but a getter that
    answered with half a dictionary would turn the next widget added to that
    window into a ``KeyError`` at render time.
    """
    return {
        "product_id": "",
        "position": "",
        "name": "",
        "label": "",
        "quantity": "",
        "price": "",
        "total": "",
        "mark": "",
    }


def line_name(line: CartLineView) -> str:
    """What to call a product whose catalog row may have gone.

    The article is the fallback because it is what the customer ordered by and
    what a manager can look up; the 1C reference is the last resort, ugly on
    purpose — an unreadable line invites removing it, which is exactly the
    thing to do with it.
    """
    return line.name or line.sku or line.product_id


def line_label(position: int, name: str) -> str:
    """The button that opens a line: its number and as much name as fits."""
    if len(name) <= MAX_LABEL_LENGTH:
        return f"{position}. {name}"

    return f"{position}. {name[: MAX_LABEL_LENGTH - 1].rstrip()}{ELLIPSIS}"


def line_mark(i18n: I18nContext, line: CartLineView) -> str:
    """What is drawn after the amount: a warning, or the stock badge.

    Never both. A product the catalog no longer holds has no stock figure worth
    printing, and "made to order" beside "gone from the catalog" reads as an
    offer to order the very thing that cannot be ordered.

    A line with no price is *not* marked here, and that is deliberate: the mark
    says "gone from the catalog", the button beside it sweeps away exactly the
    lines the catalog no longer holds, and an unpriced product is still listed.
    Saying otherwise would make the button and the mark disagree about which
    lines they mean. What such a line shows instead is "price on request" where
    its amount would be.
    """
    if not line.is_available:
        return i18n.get(text_keys.CART_LINE_UNAVAILABLE_MARK)

    return format_stock(i18n, line.stock, line.unit_name)
