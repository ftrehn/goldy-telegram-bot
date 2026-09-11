import operator

import pytest

from goldy.domain.common.values.errors import (
    NonPositiveQuantityError,
    QuantityLimitExceededError,
)
from goldy.domain.common.values.quantity import MAX_QUANTITY, Quantity
from tests.unit.factories.shop_factories import make_quantity


@pytest.mark.parametrize("value", (0, -1))
def test_a_quantity_of_nothing_does_not_exist(value: int) -> None:
    """Taking a product out of the cart is ``remove_item``, not a quantity of zero.

    A line meaning "none of this" is a line every reader downstream has to
    remember to skip.
    """
    with pytest.raises(NonPositiveQuantityError):
        make_quantity(value)


def test_the_ceiling_is_ten_thousand_pieces() -> None:
    """Spelled out here, because every other test refers to the constant.

    A shop with price types is a wholesale shop, and a thousand pieces of
    ordinary fastenings is reached on the first real order. Without this line
    the number could be taken back down to 999 with the whole run staying
    green.
    """
    assert MAX_QUANTITY == 10000


def test_a_quantity_above_the_ceiling_is_refused() -> None:
    with pytest.raises(QuantityLimitExceededError):
        make_quantity(MAX_QUANTITY + 1)


@pytest.mark.parametrize("value", (1, MAX_QUANTITY))
def test_the_boundaries_themselves_are_accepted(value: int) -> None:
    assert make_quantity(value).value == value


def test_two_quantities_add_up() -> None:
    assert make_quantity(2) + make_quantity(3) == make_quantity(5)


def test_adding_past_the_ceiling_is_refused_by_the_quantity_itself() -> None:
    """This is why ``Cart.add_item`` has no limit check of its own.

    Pressing ``+`` a thousand times is refused here, once, for every caller.
    """
    with pytest.raises(QuantityLimitExceededError):
        operator.add(make_quantity(MAX_QUANTITY), make_quantity(1))


def test_a_quantity_renders_as_a_plain_number() -> None:
    assert str(Quantity(value=7)) == "7"
