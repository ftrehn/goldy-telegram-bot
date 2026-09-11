"""What the cart screen is made of, once the joined rows have arrived.

The query is the integration suite's business. What is decided in Python is the
part that has to survive a catalog that moved under a cart standing for days:
which of the joined halves may be missing, what a missing price means, and what
the total does about it.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.infrastructure.adapters.persistence.sqlalchemy_cart_query_gateway import (
    SqlAlchemyCartQueryGateway,
)
from tests.unit.factories.cart_factories import make_cart_line_row, make_cart_line_view

GATEWAY = SqlAlchemyCartQueryGateway(AsyncSession())

ZERO = MoneyView(amount=Decimal("0.00"), currency=Currency.RUB.value)


def test_an_empty_cart_comes_to_nothing_rather_than_to_no_total() -> None:
    """The view has no optional total: "empty" has to be a zero, not a None."""
    total = GATEWAY._total_of(())

    assert total == ZERO


def test_the_total_is_the_sum_of_the_lines_that_have_a_price() -> None:
    lines = (
        make_cart_line_view(quantity=3, price="10.00"),
        make_cart_line_view(index=2, quantity=2, price="19.99"),
    )

    total = GATEWAY._total_of(lines)

    assert total == MoneyView(amount=Decimal("69.98"), currency=Currency.RUB.value)


def test_an_unpriced_line_adds_nothing_and_does_not_break_the_total() -> None:
    """A product the customer's price type does not price is browsable, not fatal."""
    lines = (
        make_cart_line_view(quantity=1, price="10.00"),
        make_cart_line_view(index=2, quantity=5, price=None),
    )

    total = GATEWAY._total_of(lines)

    assert total == MoneyView(amount=Decimal("10.00"), currency=Currency.RUB.value)


def test_a_line_left_by_a_withdrawn_product_still_counts() -> None:
    """A total that quietly shrinks is worse than one the screen explains."""
    lines = (make_cart_line_view(quantity=2, price="10.00", is_available=False),)

    total = GATEWAY._total_of(lines)

    assert total == MoneyView(amount=Decimal("20.00"), currency=Currency.RUB.value)


def test_a_cart_of_nothing_but_unpriced_lines_still_has_a_total() -> None:
    """Zero, not a crash: "price on request" is an ordinary cart, not a broken one."""
    lines = (make_cart_line_view(price=None),)

    total = GATEWAY._total_of(lines)

    assert total == ZERO


def test_a_drawn_line_multiplies_the_price_the_projection_holds_today() -> None:
    """Nothing is stored on the cart, which is what reprices it on a new list."""
    line = GATEWAY._to_line_view(make_cart_line_row(quantity=3, price="19.99"))

    assert line.quantity == 3
    assert line.unit_price == MoneyView(
        amount=Decimal("19.99"),
        currency=Currency.RUB.value,
    )
    assert line.line_total is not None
    assert line.line_total.amount == Decimal("59.97")


def test_the_value_objects_the_cart_owns_are_unwrapped_and_the_rest_is_not() -> None:
    """Two columns of this row carry type decorators, and only two.

    ``product_id`` and ``quantity`` belong to ``cart_items``; everything joined
    in comes from the Core-only projection and is already a primitive. Calling
    ``.value`` on one of those would fail on the first render.
    """
    line = GATEWAY._to_line_view(make_cart_line_row(index=7))

    assert line.product_id == "1c-product-7"
    assert line.name == "Product 7"
    assert line.sku == "SKU-7"


def test_a_line_with_no_price_under_this_price_type_loses_only_its_price() -> None:
    """A zero would read as free, and the quantity is still the customer's."""
    line = GATEWAY._to_line_view(make_cart_line_row(quantity=4, price=None))

    assert line.unit_price is None
    assert line.line_total is None
    assert line.quantity == 4
    assert line.is_priced is False


def test_a_product_withdrawn_from_the_catalog_is_marked_and_not_hidden() -> None:
    """Filtering it out inside the join would shrink the total with no word said."""
    line = GATEWAY._to_line_view(make_cart_line_row(is_active=False))

    assert line.is_available is False
    assert line.name == "Product 1"


def test_a_product_the_projection_no_longer_holds_at_all_still_draws() -> None:
    """The outer join is what keeps the line; the name is what it cannot keep."""
    line = GATEWAY._to_line_view(make_cart_line_row(product=False))

    assert line.is_available is False
    assert line.name is None
    assert line.unit_name is None
    assert line.product_id == "1c-product-1"


def test_stock_is_a_badge_and_never_a_reason_to_hide_a_line() -> None:
    """Advisory, with no reservation behind it: zero is sold to order."""
    stocked = GATEWAY._to_line_view(make_cart_line_row(stock="12.500"))
    empty = GATEWAY._to_line_view(make_cart_line_row(stock="0"))

    assert stocked.stock == Decimal("12.500")
    assert stocked.is_in_stock is True
    assert empty.is_in_stock is False
    assert empty.is_available is True
