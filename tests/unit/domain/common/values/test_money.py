import operator
from decimal import Decimal

import pytest

from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.errors import (
    CurrencyMismatchError,
    MoneyAmountOutOfRangeError,
    NegativeMoneyAmountError,
    TooPreciseMoneyAmountError,
)
from goldy.domain.common.values.money import MAX_MONEY_AMOUNT, Money
from goldy.domain.common.values.quantity import MAX_QUANTITY, Quantity
from tests.unit.factories.shop_factories import make_money, make_quantity


def test_a_price_times_a_whole_number_of_pieces_loses_no_kopecks() -> None:
    """This is why quantity is a whole number.

    Two decimal places times an integer has two decimal places exactly, so no
    rounding policy is needed and no kopeck can go missing from an order total.
    """
    total = make_money("19.99").times(make_quantity(3))

    assert total == make_money("59.97")


def test_multiplying_keeps_the_currency() -> None:
    total = make_money("10.00", Currency.USD).times(make_quantity(2))

    assert total.currency is Currency.USD


def test_amounts_add_up_exactly() -> None:
    total = make_money("0.10") + make_money("0.20")

    assert total == make_money("0.30")


def test_adding_two_currencies_is_refused() -> None:
    """The one arithmetic mistake nobody notices until the invoice."""
    roubles = make_money("100.00", Currency.RUB)
    dollars = make_money("100.00", Currency.USD)

    with pytest.raises(CurrencyMismatchError):
        operator.add(roubles, dollars)


def test_a_negative_amount_is_refused() -> None:
    with pytest.raises(NegativeMoneyAmountError):
        make_money("-0.01")


@pytest.mark.parametrize("amount", ("10.001", "0.125"))
def test_an_amount_finer_than_a_kopeck_is_refused(amount: str) -> None:
    """A third decimal place is a price we cannot charge or print."""
    with pytest.raises(TooPreciseMoneyAmountError):
        make_money(amount)


def test_an_amount_beyond_the_ceiling_is_refused() -> None:
    with pytest.raises(MoneyAmountOutOfRangeError):
        Money(MAX_MONEY_AMOUNT + Decimal("0.01"))


@pytest.mark.parametrize("amount", ("NaN", "Infinity", "-Infinity"))
def test_an_amount_that_is_not_a_number_is_refused(amount: str) -> None:
    """Checked before the comparisons, which ``NaN`` would otherwise blow up."""
    with pytest.raises(MoneyAmountOutOfRangeError):
        make_money(amount)


def test_zero_carries_two_decimal_places_and_a_currency() -> None:
    assert Money.zero() == Money(Decimal("0.00"), Currency.RUB)
    assert Money.zero(Currency.EUR).currency is Currency.EUR


def test_the_ceiling_and_the_floor_themselves_are_accepted() -> None:
    assert Money(Decimal("0.00")).amount == Decimal("0.00")
    assert Money(MAX_MONEY_AMOUNT).amount == MAX_MONEY_AMOUNT


def test_an_amount_renders_with_its_currency() -> None:
    assert str(make_money("59.97")) == "59.97 RUB"


def test_the_currency_defaults_to_roubles() -> None:
    """The shop sells in roubles; the field exists for what 1C may send later."""
    assert Money(Decimal("1.00")).currency is Currency.RUB


def test_money_is_built_positionally() -> None:
    """Mapped as a composite, which SQLAlchemy rebuilds by position.

    Making it keyword-only would break the mapping far from here, so the
    positional call is pinned down by a test rather than by a comment.
    """
    assert Money(Decimal("1.00"), Currency.USD) == Money(
        amount=Decimal("1.00"),
        currency=Currency.USD,
    )


def test_a_price_times_the_largest_quantity_stays_within_range() -> None:
    """The two ceilings have to fit each other, or a legal cart cannot be ordered."""
    total = Money(Decimal("9999.99")).times(Quantity(value=MAX_QUANTITY))

    assert total.amount == Decimal("99999900.00")
