"""How an ``OrderView`` becomes the data an order card renders with.

One module for two audiences, because it is one card. The staff card is the
customer's card plus two fields — who ordered, and whether that person is
blocked — and everything else on it is the same number, date, status, address,
recipient, comment and total, drawn the same way. Written twice, the day
somebody changes how a recipient is spelled only one of the two changes, and
the one that does not is the one nobody was looking at.

Lines arrive already rendered rather than as a list the window loops over,
because Fluent has no loop: a message per line count is not a translation, it
is a cartesian product. Which message a line is worded with is the one thing
the two audiences genuinely disagree about — the queue prints the current stock
beside the quantity ordered so that ``CONFIRMED`` means something — so the two
renderers are separate functions and the caller picks one.

Nothing here reaches for a domain type. It takes the primitives the view
already carries, which is the boundary ``MoneyView`` was flattened for.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Final

from aiogram_i18n import I18nContext

from goldy.application.common.views.order import OrderLineView, OrderView
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    MAX_PLACEABLE_LENGTH,
    MESSAGE_LIMIT,
    flag,
    for_message_text,
    format_money,
    format_order_date,
    format_order_number,
    format_quantity,
    format_stock,
)

NEXT_STEPS_STATUSES: Final[frozenset[str]] = frozenset(
    {OrderStatus.NEW.value, OrderStatus.CONFIRMED.value},
)
"""The statuses whose card still owes the buyer an explanation.

Somebody walked through five screens, saw a total and pressed a button — and in
an interface where money was expected, no money happened. The "done" screen of
checkout says what comes next, but a card opened a day later has to say it too,
and only while it is still true: once the parcel has shipped, "a manager will
call you to agree delivery" is no longer a promise but a puzzle.

Values rather than members, because a view carries its status as text.
"""

LINE_SEPARATOR: Final[str] = "\n"

TRAILING_RESERVE: Final[int] = 800
"""Room kept for the paragraphs the card itself does not contain.

A window is one message: aiogram-dialog joins every text widget in it, so the
card is followed by whichever of the next-steps line, the "cancelled by" line
and the cancellation reason applies. The reason alone may be 500 characters,
which is most of this figure; the rest is the next-steps promise and the
separators between them.

A flat reserve rather than the exact rendering of those three, because
measuring them here would mean restating in a getter the ``when`` conditions
the window already states — and a second statement of a rule is the one that
drifts. What it costs is a handful of order lines on a card long enough to be
cut anyway.
"""


def lines_budget(i18n: I18nContext, key: str, card: Mapping[str, Any]) -> int:
    """How much room the rendered lines have inside one card.

    Two ceilings, and the lower one is not Telegram's. Fluent refuses a single
    ``{ $variable }`` longer than :data:`MAX_PLACEABLE_LENGTH` by returning an
    error rather than by shortening anything, so a card whose ``$lines`` grow
    past it does not come out truncated — it does not come out. With product
    names running to 255 characters that ceiling is reached at roughly nine
    positions, while a cart is allowed a hundred.

    The message ceiling is measured rather than guessed, by rendering the card
    with no lines in it: the address and the comment are each allowed 500
    characters, so how much is left genuinely varies per order.

    Only the string values are handed over. The card also carries the booleans
    that hide its buttons, and those name nothing in the message.
    """
    skeleton = i18n.get(
        key,
        **{name: value for name, value in card.items() if isinstance(value, str)},
    )

    return min(MESSAGE_LIMIT - TRAILING_RESERVE - len(skeleton), MAX_PLACEABLE_LENGTH)


def fit_lines(i18n: I18nContext, lines: str, *, budget: int) -> str:
    """As many whole lines as fit, then a count of the ones that did not.

    Whole lines, because half a position is worse than no position: a price cut
    off mid-number is something a customer argues with a manager about.

    The count is honest rather than an ellipsis for the same reason the card is
    re-read on every render — somebody looking at a truncated order has to know
    that what they are seeing is not all of it, and how much is missing decides
    whether they phone about it.

    Room for the notice is reserved against the full number of lines, which is
    the longest the notice can ever be: the wording carries no plural branch, so
    its length only follows the digits of a count that can only shrink.
    """
    if len(lines) <= budget:
        return lines

    rows = lines.split(LINE_SEPARATOR)
    room = budget - len(
        i18n.get(text_keys.ORDER_LINES_TRUNCATED, count=len(rows)),
    )
    kept: list[str] = []
    used = 0

    for row in rows:
        needed = len(row) + len(LINE_SEPARATOR)

        if used + needed > room:
            break

        kept.append(row)
        used += needed

    notice = i18n.get(text_keys.ORDER_LINES_TRUNCATED, count=len(rows) - len(kept))

    return LINE_SEPARATOR.join([*kept, notice])


def order_card_data(
    i18n: I18nContext,
    order: OrderView,
    *,
    lines: str,
) -> dict[str, Any]:
    """Everything both cards print, including the flags that hide their buttons.

    ``lines`` is a parameter rather than something this function works out for
    itself, so that the choice between the two renderers stays visible at the
    call site — and so that no window can be handed a card without them.
    ``FluentRuntimeCore`` raises on a missing argument instead of leaving the
    placeholder in the text, so a forgotten ``lines`` is not an ugly card, it
    is no card at all.

    ``is_cancellable`` and ``is_editable`` come off the view, which computed
    them against ``CUSTOMER_CANCELLABLE_STATUSES`` and
    ``EDITABLE_ORDER_STATUSES``. Recomputing them here as ``status == "new"``
    would be a second statement of the aggregate's rule, and it would drift
    from it silently.
    """
    return {
        "number": format_order_number(i18n, order.number),
        "date": format_order_date(order.created_at, i18n.locale),
        "status": order.status,
        "address": for_message_text(order.delivery_address),
        "recipient": for_message_text(recipient_name(order)),
        "phone": order.recipient_phone_number,
        "has_comment": flag(value=bool(order.comment)),
        "comment": for_message_text(order.comment or ""),
        "lines": lines,
        "total": format_money(order.total, i18n.locale),
        "show_next_steps": order.status in NEXT_STEPS_STATUSES,
        "is_cancellable": order.is_cancellable,
        "is_editable": order.is_editable,
        "is_open": not order.is_terminal,
        "is_cancelled": order.cancelled_by is not None,
        "cancelled_by": for_message_text(order.cancelled_by or ""),
        "has_reason": bool(order.cancellation_reason),
        "reason": for_message_text(order.cancellation_reason or ""),
    }


def recipient_name(order: OrderView) -> str:
    """Who is taking delivery, as one line.

    A surname is optional here for the same reason it is optional on a profile:
    one word is a name without a surname rather than a mistake, and refusing it
    would stop an order over somebody's preference about their own name.
    """
    if order.recipient_last_name is None:
        return order.recipient_first_name

    return f"{order.recipient_first_name} {order.recipient_last_name}"


def format_order_lines(i18n: I18nContext, lines: Sequence[OrderLineView]) -> str:
    """The buyer's view of what they ordered: name, quantity, price, total."""
    return LINE_SEPARATOR.join(
        i18n.get(text_keys.ORDER_LINE, **_line_arguments(i18n, line)) for line in lines
    )


def format_queue_lines(i18n: I18nContext, lines: Sequence[OrderLineView]) -> str:
    """The same lines with today's stock beside each quantity ordered.

    That figure is the whole reason a manager can act on ``CONFIRMED`` at all:
    accepting an order is a promise to pick it, and the promise is made against
    what is on the shelf rather than against what was on it when the order was
    placed. Every other number on the line is the snapshot the order was
    written with and has deliberately not moved.
    """
    return LINE_SEPARATOR.join(
        i18n.get(
            text_keys.MANAGE_ORDERS_LINE,
            stock=format_stock(i18n, line.stock, line.unit_name),
            **_line_arguments(i18n, line),
        )
        for line in lines
    )


def _line_arguments(i18n: I18nContext, line: OrderLineView) -> dict[str, str]:
    """What the two line messages have in common, worded once."""
    return {
        "position": str(line.position),
        "name": for_message_text(line.name),
        "quantity": format_quantity(line.quantity, line.unit_name),
        "price": format_money(line.unit_price, i18n.locale),
        "total": format_money(line.line_total, i18n.locale),
    }
