"""The two decisions checkout makes that nobody would see go wrong.

Whether the confirmation screen noticed that the cart moved under it — which is
the only explanation a refused order gets — and whether the screens that embed
another message hand it the arguments it reads. The second is not cosmetic: the
Fluent core raises on an unknown external, so a "done" screen missing the phone
number renders nothing at all, right after the money was agreed.
"""

from decimal import Decimal

from aiogram_i18n import I18nContext

from goldy.application.common.views.cart import CartView
from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.presentation.telegram.common import text_keys
from goldy.presentation.telegram.common.formatting import NO, YES
from goldy.presentation.telegram.handlers.checkout.getters import (
    FIRST_NAME_KEY,
    LAST_NAME_KEY,
    recipient_name,
    remember_totals,
)
from tests.unit.factories.cart_factories import make_cart_line_view

PHONE = "+79991234567"


def _cart(total: str, lines: int = 1) -> CartView:
    return CartView(
        lines=tuple(make_cart_line_view(index) for index in range(1, lines + 1)),
        total=MoneyView(amount=Decimal(total), currency=Currency.RUB.value),
    )


def test_the_first_confirmation_reports_nothing_moved() -> None:
    """A cart cannot have been repriced before it was ever printed."""
    window_data: dict[str, object] = {}

    assert remember_totals(window_data, _cart("100.00")) is False


def test_a_total_that_moved_between_renders_is_reported() -> None:
    """This is the whole of the notice a refused confirmation shows.

    The command refuses an order worth something other than the screen said,
    and the screen redraws with the new number. Without this, the only visible
    change would be a figure the person had no reason to read twice.
    """
    window_data: dict[str, object] = {}
    remember_totals(window_data, _cart("100.00"))

    assert remember_totals(window_data, _cart("120.00")) is True


def test_the_new_total_is_reported_once_and_not_again() -> None:
    """The notice describes a change, so it goes away when nothing changes."""
    window_data: dict[str, object] = {}
    remember_totals(window_data, _cart("100.00"))
    remember_totals(window_data, _cart("120.00"))

    assert remember_totals(window_data, _cart("120.00")) is False


def test_a_line_leaving_the_cart_counts_even_at_the_same_total() -> None:
    """Two prices can move in opposite directions and leave the sum alone.

    What the customer is buying has still changed, and the command refuses on
    the line count for exactly that reason.
    """
    window_data: dict[str, object] = {}
    remember_totals(window_data, _cart("100.00", lines=2))

    assert remember_totals(window_data, _cart("100.00", lines=1)) is True


def test_a_recipient_without_a_surname_is_written_as_one_word() -> None:
    """One word is no surname rather than an error — delivery slips say so."""
    assert recipient_name({FIRST_NAME_KEY: "Мария", LAST_NAME_KEY: None}) == "Мария"


def test_a_recipient_with_a_surname_is_written_as_two() -> None:
    data = {FIRST_NAME_KEY: "Мария", LAST_NAME_KEY: "Иванова"}

    assert recipient_name(data) == "Мария Иванова"


def test_the_done_screen_passes_the_phone_to_the_promise_it_embeds(
    russian: I18nContext,
) -> None:
    """``checkout-done`` names no phone; the message it references does.

    A referenced message is rendered in the caller's scope, so the argument has
    to be handed to the caller — and a missing one raises rather than printing
    itself, which would leave the customer with nothing at all on the one
    screen that explains how they will be contacted.
    """
    text = russian.get(text_keys.CHECKOUT_DONE, number="№ 000123", phone=PHONE)

    assert PHONE in text
    assert "000123" in text


def test_an_order_without_a_comment_says_so_rather_than_showing_a_blank(
    russian: I18nContext,
) -> None:
    """The selector branches on the word the flag helper spells, not on truth."""
    text = russian.get(
        text_keys.CHECKOUT_CONFIRM,
        address="Москва, Тверская 1",
        recipient="Мария Иванова",
        phone=PHONE,
        has_comment=NO,
        comment="",
        count=2,
        total="100,00 ₽",
    )

    assert "Комментарий: нет" in text


def test_a_comment_is_shown_when_there_is_one(russian: I18nContext) -> None:
    text = russian.get(
        text_keys.CHECKOUT_CONFIRM,
        address="Москва, Тверская 1",
        recipient="Мария Иванова",
        phone=PHONE,
        has_comment=YES,
        comment="Позвонить за час",
        count=2,
        total="100,00 ₽",
    )

    assert "Позвонить за час" in text
