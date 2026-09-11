from datetime import UTC, datetime
from decimal import Decimal

import pytest
from aiogram_i18n import I18nContext

from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.presentation.telegram.common.formatting import (
    NARROW_NO_BREAK_SPACE,
    NumberStyle,
    format_money,
    format_order_date,
    format_order_number,
    format_order_status,
    format_price,
    format_quantity,
    format_stock,
    format_stock_amount,
)


def test_an_amount_is_drawn_with_its_currency_sign() -> None:
    money = MoneyView(amount=Decimal("1234.50"), currency=Currency.RUB.value)

    assert format_money(money) == f"1{NARROW_NO_BREAK_SPACE}234,50 ₽"


def test_english_writes_the_same_amount_its_own_way() -> None:
    money = MoneyView(amount=Decimal("1234.50"), currency=Currency.RUB.value)

    assert format_money(money, "en") == "1,234.50 ₽"


def test_a_round_price_keeps_both_decimals() -> None:
    """A price shown as "12,5 ₽" reads as an approximation of one."""
    money = MoneyView(amount=Decimal("12.5"), currency=Currency.RUB.value)

    assert format_money(money) == "12,50 ₽"


def test_a_style_that_groups_with_a_dot_keeps_its_own_separators() -> None:
    """Pins the one way a two-pass replacement quietly corrupts a price.

    No locale here groups thousands with a dot today, but several languages do,
    and adding one is a single row in ``NUMBER_STYLES``. Swapping the
    separators with two sequential replacements would then let the second pass
    rewrite what the first had just written — ``1.234,50`` coming out as
    ``1,234,50``, which is not a wrong-looking price but a different number.
    """
    style = NumberStyle(group=".", decimal=",")

    assert style.apply(Decimal("1234.50")) == "1.234,50"


def test_a_currency_with_no_sign_falls_back_to_its_code() -> None:
    money = MoneyView(amount=Decimal("10.00"), currency="chf")

    assert format_money(money) == "10,00 CHF"


def test_a_missing_price_is_words_rather_than_a_zero(russian: I18nContext) -> None:
    """Rendering nothing as "0 ₽" would read as "free", and nobody queries that."""
    assert format_price(russian, None) == "Цена по запросу"


def test_a_present_price_is_drawn_as_money(russian: I18nContext) -> None:
    money = MoneyView(amount=Decimal("99.00"), currency=Currency.RUB.value)

    assert format_price(russian, money) == "99,00 ₽"


@pytest.mark.parametrize(
    ("quantity", "unit_name", "expected"),
    (
        (2, "шт", "2 шт"),
        (3, "м", "3 м"),
        (5, None, "5"),
    ),
)
def test_a_quantity_carries_the_unit_it_is_counted_in(
    quantity: int,
    unit_name: str | None,
    expected: str,
) -> None:
    assert format_quantity(quantity, unit_name) == expected


def test_stock_on_the_shelf_is_shown_as_a_count(russian: I18nContext) -> None:
    assert format_stock(russian, Decimal("12.000"), "шт") == "В наличии: 12 шт"


def test_stock_at_zero_is_sold_to_order(russian: I18nContext) -> None:
    """Never hidden and never refused — that is what the badge is for."""
    assert format_stock(russian, Decimal(0), "шт") == "Под заказ"


def test_unknown_stock_is_sold_to_order_too(russian: I18nContext) -> None:
    assert format_stock(russian, None, "шт") == "Под заказ"


def test_a_fractional_stock_keeps_its_decimals(russian: I18nContext) -> None:
    assert format_stock(russian, Decimal("1.5"), "м") == "В наличии: 1.5 м"


def test_a_bare_stock_figure_drops_the_zeros_1c_sends_with_it() -> None:
    """What the product card needs, which the badge cannot give it.

    ``catalog-card`` embeds ``stock-badge``, and an embedded Fluent message
    reads the arguments of the message that referenced it — so the card has to
    pass ``$stock`` as the number itself and cannot pass the finished badge.
    """
    assert format_stock_amount(Decimal("12.000")) == "12"


def test_a_bare_stock_figure_sold_by_the_metre_keeps_its_fraction() -> None:
    assert format_stock_amount(Decimal("2.50")) == "2.5"


def test_an_unknown_stock_figure_prints_nothing() -> None:
    """The badge's other branch speaks for that case, so the number stays out."""
    assert not format_stock_amount(None)


def test_an_order_number_is_decorated_by_the_locale(russian: I18nContext) -> None:
    assert format_order_number(russian, "1043") == "№ 1043"


def test_a_date_is_drawn_to_the_minute() -> None:
    moment = datetime(2026, 9, 11, 14, 35, 59, tzinfo=UTC)

    assert format_order_date(moment) == "11.09.2026 14:35"


def test_a_known_status_is_translated(russian: I18nContext) -> None:
    assert format_order_status(russian, "shipped") == "отгружен"


@pytest.mark.parametrize("status", tuple(OrderStatus))
def test_every_status_an_order_can_reach_is_worded_in_russian(
    status: OrderStatus,
    russian: I18nContext,
) -> None:
    """The dictionary and the enum are joined by nothing but this.

    ``order-status`` is one message with a selector, and its ``*[other]``
    branch prints the raw value — which is the right answer for a status 1C
    invents and the wrong one for a status this bot itself sets. A member added
    to ``OrderStatus`` without a variant beside it therefore shows a Russian
    customer the English word ``shipped`` in the middle of their order card,
    and nothing fails anywhere: the screen renders, the enum is complete, the
    two languages still define the same keys.
    """
    assert format_order_status(russian, status.value) != status.value


def test_an_unknown_status_prints_itself(russian: I18nContext) -> None:
    """A status 1C grows later is ugly on screen; calling it "new" is a lie."""
    assert format_order_status(russian, "packed") == "packed"


def test_a_language_the_shop_has_no_style_for_is_written_the_shop_s_own_way() -> None:
    """A price is the one thing on a screen that must never be missing.

    ``MAX`` arrives with its own locale strings, and a person whose messenger
    says ``de`` would otherwise be answered with a ``KeyError`` where the money
    should be. Grouping the thousands the wrong way is the whole cost of the
    fallback.
    """
    money = MoneyView(amount=Decimal("1234.50"), currency=Currency.RUB.value)

    assert format_money(money, "de") == format_money(money)


def test_english_writes_a_date_the_way_english_sorts_it() -> None:
    moment = datetime(2026, 9, 11, 14, 35, tzinfo=UTC)

    assert format_order_date(moment, "en") == "2026-09-11 14:35"
