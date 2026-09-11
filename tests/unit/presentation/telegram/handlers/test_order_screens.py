"""The two order dialogs, checked where they can fail without anybody noticing.

A window is built at import time out of a Fluent key and a handful of
placeholders, and nothing connects it to the getter that fills them in. Two
mistakes are therefore invisible to the type checker, to the linter and to
every other test in this suite.

The first is a message argument the window never passes. ``FluentRuntimeCore``
does not leave ``{ $status }`` in the text — it raises ``FluentMessageError``,
so a card missing one argument is not an ugly card, it is no card at all. The
risk is concentrated in exactly the keys that embed another message, because a
referenced message resolves in the caller's scope and quietly adds its own
arguments to the caller's bill: ``order-card`` owes the arguments of
``order-status``, and ``manage-orders-card`` owes them too.

The second is a placeholder the getter does not produce, which fails as a
``KeyError`` deep inside a render nobody is watching.

Both are checked here against the real ``.ftl`` files and against the real
getter output, rather than against a copy of either.
"""

import re
from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
from typing import Any, Final

import pytest
from aiogram.fsm.state import State
from aiogram_dialog import Dialog
from aiogram_dialog.widgets.text import Format, Text
from aiogram_i18n import I18nContext
from aiogram_i18n.cores import BaseCore

from goldy.domain.carts.entities.cart import MAX_CART_LINES
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.locale import SUPPORTED_LOCALES
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import (
    MAX_PLACEABLE_LENGTH,
    MESSAGE_LIMIT,
)
from goldy.presentation.telegram.common.order_cards import (
    fit_lines,
    format_order_lines,
    format_queue_lines,
    lines_budget,
    order_card_data,
)
from goldy.presentation.telegram.common.paging import DEFAULT_PAGE_SIZE, Paging
from goldy.presentation.telegram.common.widgets import I18NFormat
from goldy.presentation.telegram.handlers.manage_orders import (
    MANAGE_ORDERS_DIALOG,
    ManageOrdersStates,
)
from goldy.presentation.telegram.handlers.orders import ORDERS_DIALOG, OrdersStates
from goldy.presentation.telegram.handlers.orders.getters import (
    repeat_confirm_data,
    repeat_result_data,
)
from tests.unit.factories.order_factories import (
    make_order_line_view,
    make_order_view,
)

LOCALES: Final[tuple[str, ...]] = tuple(sorted(SUPPORTED_LOCALES))

PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")
"""How a ``Format`` names the window datum it wants."""

SAMPLE: Final[str] = "sample"
"""Stands in for every argument when only the argument's presence is at stake."""

STOCK_ON_THE_SHELF: Final[Decimal] = Decimal(37)
"""A number that appears nowhere else on a line, so finding it means something."""


def _widgets(node: object) -> Iterator[object]:
    """Every widget under this one, labels of buttons included."""
    yield node

    for attribute in ("texts", "buttons"):
        for child in getattr(node, attribute, ()):
            yield from _widgets(child)

    label = getattr(node, "text", None)

    if isinstance(label, Text):
        yield from _widgets(label)


def _formats(dialog: Dialog, state: State | None = None) -> tuple[I18NFormat, ...]:
    """The translated texts of one window, or of the whole dialog."""
    windows = dialog.windows.values() if state is None else (dialog.windows[state],)

    return tuple(
        widget
        for window in windows
        for root in (window.text, window.keyboard)
        for widget in _widgets(root)
        if isinstance(widget, I18NFormat)
    )


def _wanted_data(dialog: Dialog, state: State) -> set[str]:
    """Which window data a screen reads, taken from its own placeholders."""
    return {
        name
        for widget in _formats(dialog, state)
        for value in widget.mapping.values()
        if isinstance(value, Format)
        for name in PLACEHOLDER.findall(value.text)
    }


def _render(
    core: BaseCore[Any],
    widget: I18NFormat,
    locale: str,
    data: dict[str, Any],
) -> str:
    """Renders one window text the way ``I18NFormat`` will at runtime."""
    arguments = {
        name: value.text.format(**data) if isinstance(value, Format) else value
        for name, value in widget.mapping.items()
    }

    return core.get(widget.text, locale, **arguments)


def _card_data(i18n: I18nContext) -> dict[str, Any]:
    order = make_order_view()

    return order_card_data(
        i18n,
        order,
        lines=format_order_lines(i18n, order.lines),
    )


def _queue_card_data(i18n: I18nContext) -> dict[str, Any]:
    order = make_order_view()

    return {
        **order_card_data(
            i18n,
            order,
            lines=format_queue_lines(i18n, order.lines),
        ),
        "customer": SAMPLE,
        "blocked_mark": "",
    }


def _list_data() -> dict[str, Any]:
    return {
        **Paging(number=0, size=DEFAULT_PAGE_SIZE, total=3).as_data(),
        "filter": SAMPLE,
    }


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize(
    "dialog",
    (ORDERS_DIALOG, MANAGE_ORDERS_DIALOG),
    ids=("orders", "manage_orders"),
)
def test_every_window_passes_the_arguments_its_message_needs(
    dialog: Dialog,
    locale: str,
    i18n_core: BaseCore[Any],
) -> None:
    """Because a missing one is a screen that does not render at all.

    ``order-card`` and ``manage-orders-card`` each embed ``order-status``, and
    a referenced message reads the arguments of whoever referenced it. Nothing
    in the window says so — the key looks like a key with four placeholders and
    is in fact a key with five.
    """
    rendered = [
        i18n_core.get(widget.text, locale, **dict.fromkeys(widget.mapping, SAMPLE))
        for widget in _formats(dialog)
    ]

    assert all(text.strip() for text in rendered)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_customers_card_renders_from_what_its_getter_builds(
    locale: str,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    """The window and the getter, joined the way the dialog will join them."""
    data = _card_data(russian)

    rendered = [
        _render(i18n_core, widget, locale, data)
        for widget in _formats(ORDERS_DIALOG, OrdersStates.CARD)
    ]

    assert all(text.strip() for text in rendered)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_staff_card_renders_from_what_its_getter_builds(
    locale: str,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    data = _queue_card_data(russian)

    rendered = [
        _render(i18n_core, widget, locale, data)
        for widget in _formats(MANAGE_ORDERS_DIALOG, ManageOrdersStates.CARD)
    ]

    assert all(text.strip() for text in rendered)


def test_the_cancellation_screen_names_the_order_its_card_was_showing(
    russian: I18nContext,
) -> None:
    """It shares the card's getter, so it cannot name a different one."""
    wanted = _wanted_data(ORDERS_DIALOG, OrdersStates.CANCEL_CONFIRM)

    assert wanted <= set(_card_data(russian))


@pytest.mark.parametrize(
    ("dialog", "state"),
    (
        (ORDERS_DIALOG, OrdersStates.LIST),
        (MANAGE_ORDERS_DIALOG, ManageOrdersStates.QUEUE),
    ),
    ids=("orders", "manage_orders"),
)
def test_a_list_window_reads_only_what_the_pager_puts_there(
    dialog: Dialog,
    state: State,
) -> None:
    """The counters on a list heading come from ``paging_data`` and nowhere else.

    Spelled by hand in a getter, "page 1 of 0" is one edit away, which is why
    the arithmetic moved into the shared pager in the first place.
    """
    assert _wanted_data(dialog, state) <= set(_list_data())


@pytest.mark.parametrize("status", tuple(OrderStatus))
def test_next_steps_are_promised_only_while_they_are_still_true(
    status: OrderStatus,
    russian: I18nContext,
) -> None:
    """A promise to call about delivery is a lie once the parcel has shipped.

    The line exists because the buyer pressed a button where money was expected
    and no money happened. Once the parcel has left, the sentence stops
    explaining anything and starts contradicting the status above it.
    """
    order = make_order_view(status=status)

    data = order_card_data(russian, order, lines="")

    assert data["show_next_steps"] is (status in {OrderStatus.NEW, OrderStatus.CONFIRMED})


def test_a_finished_order_offers_no_status_to_move_to(russian: I18nContext) -> None:
    """``COMPLETED`` and ``CANCELLED`` have no transitions left in the table.

    A "change status" button over an empty picker looks like the screen is
    broken, which is worse than the button not being there.
    """
    order = make_order_view(
        status=OrderStatus.COMPLETED,
        is_cancellable=False,
        is_editable=False,
        is_terminal=True,
    )

    data = order_card_data(russian, order, lines="")

    assert data["is_open"] is False


def test_the_queue_line_carries_todays_stock_and_the_buyers_does_not(
    russian: I18nContext,
) -> None:
    """That join is the whole reason a manager can act on ``CONFIRMED``.

    Accepting an order is a promise to pick it, and the promise is made against
    what is on the shelf rather than against what was on it when the order was
    placed. Every other figure on the line is the snapshot, and has moved for
    nobody.
    """
    line = replace(make_order_line_view(), stock=STOCK_ON_THE_SHELF)

    for_staff = format_queue_lines(russian, (line,))
    for_buyer = format_order_lines(russian, (line,))

    assert str(STOCK_ON_THE_SHELF.to_integral_value()) in for_staff
    assert str(STOCK_ON_THE_SHELF.to_integral_value()) not in for_buyer


def test_the_card_never_asks_for_an_order_number_it_has_not_decorated(
    russian: I18nContext,
) -> None:
    """Presentation decorates the number; the domain has never heard of a sign.

    Both languages write one, and they do not write the same one — which is why
    it is a message rather than an f-string, and why the card is handed the
    decorated string rather than the raw number.
    """
    data = _card_data(russian)

    assert data["number"] == russian.get(
        text_keys.ORDER_NUMBER,
        number=make_order_view().number,
    )


MAX_PRODUCT_NAME: Final[str] = "Б" * 255
"""A name the length 1C is allowed to send, which is where the card breaks."""


def _long_order(count: int) -> Any:
    lines = tuple(
        replace(make_order_line_view(position=index, index=index), name=MAX_PRODUCT_NAME)
        for index in range(1, count + 1)
    )

    return make_order_view(lines=lines)


@pytest.mark.parametrize("locale", LOCALES)
def test_a_hundred_line_order_still_has_a_card(
    locale: str,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    """The ceiling that breaks this card is Fluent's, and it is not 4096.

    ``fluent.runtime`` refuses a placeable over 2500 characters by failing the
    whole message instead of shortening it, and both cards join every line of
    the order into one argument. A cart may hold a hundred positions and a
    product name 255 characters, so an ordinary wholesale order made the card
    raise ``FluentMessageError`` — the buyer could not open their own order and
    neither could the manager who had to pick it.
    """
    order = _long_order(MAX_CART_LINES)
    card = order_card_data(russian, order, lines="")
    lines = fit_lines(
        russian,
        format_order_lines(russian, order.lines),
        budget=lines_budget(russian, text_keys.ORDER_CARD, card),
    )

    rendered = [
        _render(i18n_core, widget, locale, {**card, "lines": lines})
        for widget in _formats(ORDERS_DIALOG, OrdersStates.CARD)
    ]

    assert all(text.strip() for text in rendered)
    assert max(len(text) for text in rendered) <= MESSAGE_LIMIT


def test_a_truncated_card_says_how_many_positions_it_left_out(
    russian: I18nContext,
) -> None:
    """An ellipsis would hide the one fact that decides whether to phone."""
    order = _long_order(MAX_CART_LINES)
    card = order_card_data(russian, order, lines="")
    budget = lines_budget(russian, text_keys.ORDER_CARD, card)

    lines = fit_lines(russian, format_order_lines(russian, order.lines), budget=budget)
    shown = sum(1 for row in lines.split("\n") if MAX_PRODUCT_NAME in row)

    assert len(lines) <= budget
    assert 0 < shown < MAX_CART_LINES
    assert lines.endswith(
        russian.get(text_keys.ORDER_LINES_TRUNCATED, count=MAX_CART_LINES - shown),
    )


def test_a_short_order_keeps_every_line(russian: I18nContext) -> None:
    """Truncation must not be the ordinary case: most orders are three lines."""
    order = make_order_view()
    rendered = format_order_lines(russian, order.lines)
    card = order_card_data(russian, order, lines="")

    fitted = fit_lines(
        russian,
        rendered,
        budget=lines_budget(russian, text_keys.ORDER_CARD, card),
    )

    assert fitted == rendered


@pytest.mark.parametrize("locale", LOCALES)
def test_the_staff_card_of_a_hundred_line_order_renders_too(
    locale: str,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    """Its lines carry a stock figure, so it runs out of room sooner."""
    order = _long_order(MAX_CART_LINES)
    card = {
        **order_card_data(russian, order, lines=""),
        "customer": SAMPLE,
        "blocked_mark": "",
    }
    lines = fit_lines(
        russian,
        format_queue_lines(russian, order.lines),
        budget=lines_budget(russian, text_keys.MANAGE_ORDERS_CARD, card),
    )

    rendered = [
        _render(i18n_core, widget, locale, {**card, "lines": lines})
        for widget in _formats(MANAGE_ORDERS_DIALOG, ManageOrdersStates.CARD)
    ]

    assert all(text.strip() for text in rendered)
    assert max(len(text) for text in rendered) <= MESSAGE_LIMIT


CART_POSITIONS: Final[int] = 8
"""A count that appears nowhere in the order number, so finding it means something."""


@pytest.mark.parametrize("locale", LOCALES)
def test_the_repeat_confirmation_says_what_becomes_of_a_full_cart(
    locale: str,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    """Both sides of the selector, because only one of them is ever drawn.

    A repeat into an empty cart needs no explanation, and that branch of the
    message is empty on purpose. A repeat into a cart somebody was assembling
    is a promise about what happens to those positions — and a promise that
    fails to render is worse than one that was never made, because Fluent
    answers a broken selector by dropping the whole message.
    """
    order = make_order_view()
    widget = _confirmation_of(OrdersStates.REPEAT_CONFIRM, text_keys.ORDER_REPEAT_CONFIRM)

    empty = _render(i18n_core, widget, locale, repeat_confirm_data(russian, order, 0))
    filled = _render(
        i18n_core,
        widget,
        locale,
        repeat_confirm_data(russian, order, CART_POSITIONS),
    )

    assert empty.strip()
    assert filled.startswith(empty.strip())
    assert str(CART_POSITIONS) in filled
    assert str(CART_POSITIONS) not in empty


def _confirmation_of(state: State, key: str) -> I18NFormat:
    """The one text of a window written with this key, buttons excluded."""
    return next(widget for widget in _formats(ORDERS_DIALOG, state) if widget.text == key)


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("moved", (0, 2), ids=("nothing-moved", "some-moved"))
def test_the_repeat_result_renders_whichever_outcome_it_is_drawn_for(
    locale: str,
    moved: int,
    russian: I18nContext,
    i18n_core: BaseCore[Any],
) -> None:
    """One window, two mutually exclusive texts, and no third outcome here.

    A repeat that carried everything over never reaches this screen — it is
    answered with a toast — so the window has to be legible both when something
    was left behind and when nothing could be taken at all.
    """
    data = repeat_result_data(russian, moved, ("Товар 3", "Товар 4"))

    rendered = [
        _render(i18n_core, widget, locale, data)
        for widget in _formats(ORDERS_DIALOG, OrdersStates.REPEAT_RESULT)
    ]

    assert all(text.strip() for text in rendered)
    assert data["moved_some"] is not data["moved_nothing"]


def test_a_hundred_withdrawn_products_still_fit_in_one_message(
    russian: I18nContext,
) -> None:
    """The skipped list is a single placeable, which is where Fluent gives up.

    A wholesale order of a hundred positions whose supplier has gone is exactly
    the case this screen exists for, and every one of those names may be the
    255 characters 1C allows. Unshortened the message does not come out
    truncated — it does not come out, and the person is left with no idea what
    happened to their repeat.
    """
    skipped = (MAX_PRODUCT_NAME,) * MAX_CART_LINES

    data = repeat_result_data(russian, 0, skipped)

    assert len(data["skipped"]) <= MAX_PLACEABLE_LENGTH
    assert russian.get(
        text_keys.ORDER_REPEAT_PARTIAL,
        moved=data["moved"],
        skipped=data["skipped"],
    ).strip()
