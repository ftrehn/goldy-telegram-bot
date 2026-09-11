import pytest

from goldy.domain.carts.entities.cart import MAX_CART_LINES
from goldy.domain.carts.errors import (
    CartLineLimitExceededError,
    CartLineNotFoundError,
    EmptyCartError,
)
from goldy.domain.common.values.errors import QuantityLimitExceededError
from goldy.domain.common.values.quantity import MAX_QUANTITY
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.factories.shop_factories import (
    make_cart,
    make_product_id,
    make_quantity,
)
from tests.unit.support import emitted_event_names


def test_a_new_cart_belongs_to_a_person_and_holds_nothing() -> None:
    cart = make_cart(user_id=make_user_id())

    assert cart.user_id == make_user_id()
    assert cart.is_empty is True
    assert cart.line_count == 0


def test_adding_a_product_puts_one_line_in() -> None:
    cart = make_cart()

    cart.add_item(make_product_id(1), make_quantity(2))

    assert cart.line_count == 1
    assert cart.total_quantity == 2


def test_adding_the_same_product_again_raises_the_quantity() -> None:
    """One product is one line — the primary key of the table says so too."""
    cart = make_cart({1: 2})

    cart.add_item(make_product_id(1), make_quantity(3))

    assert cart.line_count == 1
    assert cart.total_quantity == 5


def test_adding_more_than_a_line_may_hold_is_refused() -> None:
    cart = make_cart({1: MAX_QUANTITY})

    with pytest.raises(QuantityLimitExceededError):
        cart.add_item(make_product_id(1), make_quantity(1))


def test_a_refused_addition_leaves_the_line_as_it_was() -> None:
    cart = make_cart({1: MAX_QUANTITY})

    with pytest.raises(QuantityLimitExceededError):
        cart.add_item(make_product_id(1), make_quantity(1))

    assert cart.total_quantity == MAX_QUANTITY


def test_a_cart_stops_at_a_hundred_different_products() -> None:
    """The limit is on distinct products, not on pieces."""
    cart = make_cart(dict.fromkeys(range(1, MAX_CART_LINES + 1), 1))

    with pytest.raises(CartLineLimitExceededError):
        cart.add_item(make_product_id(MAX_CART_LINES + 1), make_quantity(1))


def test_a_full_cart_still_takes_more_of_what_is_already_in_it() -> None:
    cart = make_cart(dict.fromkeys(range(1, MAX_CART_LINES + 1), 1))

    cart.add_item(make_product_id(1), make_quantity(4))

    assert cart.line_count == MAX_CART_LINES
    assert cart.total_quantity == MAX_CART_LINES + 4


def test_decreasing_a_line_takes_one_piece_off_it() -> None:
    """The minus button moves by one, the way the plus button does."""
    cart = make_cart({1: 3})

    cart.decrease_item(make_product_id(1))

    assert cart.total_quantity == 2
    assert cart.line_count == 1


def test_decreasing_the_last_piece_takes_the_whole_line_out() -> None:
    """So the minus button need not know that at one it means "remove".

    ``Quantity`` has no zero by construction, so one less than one can only be
    expressed as the line going away — and the button is spared having to guess
    the current quantity from a keyboard drawn two seconds ago.
    """
    cart = make_cart({1: 1, 2: 2})

    cart.decrease_item(make_product_id(1))

    assert cart.line_for(make_product_id(1)) is None
    assert cart.line_count == 1


def test_decreasing_something_not_in_the_cart_is_refused() -> None:
    cart = make_cart({1: 1})

    with pytest.raises(CartLineNotFoundError):
        cart.decrease_item(make_product_id(2))


def test_setting_a_quantity_replaces_it_rather_than_adding_to_it() -> None:
    """The keypad screen shows an absolute number, so it must set one."""
    cart = make_cart({1: 5})

    cart.set_item_quantity(make_product_id(1), make_quantity(2))

    assert cart.total_quantity == 2


def test_setting_the_quantity_of_something_not_in_the_cart_is_refused() -> None:
    cart = make_cart({1: 1})

    with pytest.raises(CartLineNotFoundError):
        cart.set_item_quantity(make_product_id(2), make_quantity(1))


def test_removing_a_product_takes_its_whole_line_out() -> None:
    cart = make_cart({1: 3, 2: 1})

    cart.remove_item(make_product_id(1))

    assert cart.line_count == 1
    assert cart.line_for(make_product_id(1)) is None


def test_removing_something_not_in_the_cart_is_refused() -> None:
    cart = make_cart({1: 1})

    with pytest.raises(CartLineNotFoundError):
        cart.remove_item(make_product_id(2))


def test_clearing_empties_everything_at_once() -> None:
    cart = make_cart({1: 1, 2: 2, 3: 3})

    cart.clear()

    assert cart.is_empty is True


def test_clearing_an_already_empty_cart_is_not_a_failure() -> None:
    """A cart already in the state asked for is not a reason to fail.

    Checkout calls this, and refusing here would fail an order that otherwise
    went through.
    """
    cart = make_cart()

    cart.clear()

    assert cart.is_empty is True


def test_an_empty_cart_cannot_be_ordered() -> None:
    cart = make_cart()

    with pytest.raises(EmptyCartError):
        cart.ensure_not_empty()


def test_a_cart_with_something_in_it_passes_the_checkout_guard() -> None:
    cart = make_cart({1: 1})

    cart.ensure_not_empty()


def test_total_quantity_counts_pieces_and_line_count_counts_products() -> None:
    cart = make_cart({1: 3, 2: 4})

    assert cart.line_count == 2
    assert cart.total_quantity == 7


def test_the_cart_records_nothing_whatever_is_done_to_it() -> None:
    """Editing a draft is not a fact anyone reacts to.

    Everything an aggregate records is drained into the outbox and published;
    pressing ``+`` three times and ``-`` once would put four messages on a
    queue nobody consumes. The single business fact here is ``OrderPlaced``.
    """
    cart = make_cart()

    cart.add_item(make_product_id(1), make_quantity(1))
    cart.add_item(make_product_id(1), make_quantity(1))
    cart.decrease_item(make_product_id(1))
    cart.set_item_quantity(make_product_id(1), make_quantity(5))
    cart.remove_item(make_product_id(1))
    cart.clear()

    assert emitted_event_names(cart.events_collection) == []
