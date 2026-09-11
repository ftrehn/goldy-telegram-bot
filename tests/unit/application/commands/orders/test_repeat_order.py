"""Repeating an order: what still sells, what does not, and whose order it is.

Every one of these tests is about the gap ADR-0003 opened deliberately. An
order line is a snapshot taken months ago, the catalog has moved since, and the
repeat is the one place in the shop that has to reconcile the two — carrying
over what can be bought today, at today's price, and saying plainly what it
could not carry.

Lives beside the other order commands rather than under ``commands/carts``,
where the handler itself lives, because what has to be arranged for each of
these is an order: a customer who owns one, lines pointing at products the
catalog may or may not still hold, and somebody else's order to be refused.
That arrangement is already in the conftest here.

The three reasons a line is left behind are only two shapes at this level, and
that is the pricing port's contract rather than an omission: a product the
import dropped and a product a sweep deactivated are both simply missing from
the answer, because the adapter filters on ``is_active`` in the same query.
Only "no price under this price list" comes back as a row.
"""

import pytest

from goldy.application.commands.carts.repeat_order.command import RepeatOrderCommand
from goldy.application.commands.carts.repeat_order.handler import RepeatOrderHandler
from goldy.application.error import OrderNotFoundError
from goldy.domain.carts.entities.cart import MAX_CART_LINES
from goldy.domain.carts.errors import CartLineLimitExceededError
from goldy.domain.orders.entities.order import Order
from goldy.domain.users.errors import AuthorizationError
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.factories.order_factories import make_priced_product_view
from tests.unit.factories.shop_factories import make_order_id, make_order_line
from tests.unit.stubs.catalog import StubPricingGateway
from tests.unit.stubs.orders import InMemoryCartCommandGateway

from .conftest import CartSeeder, OrderSeeder

TWO_LINES = (
    make_order_line(position=1, index=1, quantity=2),
    make_order_line(position=2, index=2, quantity=3),
)
"""Product 1 twice and product 2 three times, which is an ordinary small order."""

SECOND_PRODUCT_NAME = "Товар 2"
"""How the builders name product 2, which is how its order line names it."""


def repeat(order: Order) -> RepeatOrderCommand:
    """The command as the confirmation screen sends it, naming one order."""
    return RepeatOrderCommand(order_id=order.id)


def quantities(cart_gateway: InMemoryCartCommandGateway) -> dict[str, int]:
    """What is in the only cart anybody seeded, by product and by count."""
    cart = next(iter(cart_gateway.carts.values()))

    return {line.product_id.value: line.quantity.value for line in cart.lines}


async def test_an_order_that_still_sells_goes_back_in_the_cart_whole(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    view = await repeat_order_handler.handle(repeat(order))

    assert view.moved_line_count == 2
    assert view.skipped_product_names == ()
    assert view.moved_everything
    assert quantities(cart_gateway) == {"1c-product-1": 2, "1c-product-2": 3}
    assert [line.quantity.value for line in order.lines] == [2, 3]


async def test_the_price_is_read_afresh_and_never_taken_from_the_snapshot(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """The one thing ADR-0003 forbids outright, and how it is held.

    The price on an order line is what was agreed last spring; the repeat is a
    fresh purchase at whatever the shop charges today. Half of that is
    structural — the cart has nowhere to put a price, so nothing can be copied
    into it — and the other half is this: the customer's own price list is
    resolved on every repeat, through the port that must never be cached,
    because a product falls out of the repeat precisely when *their* price list
    stops covering it.
    """
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1, price="1000.00"),
        make_priced_product_view(2, price="1000.00"),
    )

    await repeat_order_handler.handle(repeat(order))

    assert pricing_gateway.asked_for == [customer.id]


async def test_a_product_the_catalog_has_lost_is_left_behind_by_name(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """Named off the snapshot, because nowhere else still holds the name."""
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (make_priced_product_view(1),)

    view = await repeat_order_handler.handle(repeat(order))

    assert view.moved_line_count == 1
    assert view.skipped_product_names == (SECOND_PRODUCT_NAME,)
    assert not view.moved_everything
    assert quantities(cart_gateway) == {"1c-product-1": 2}


async def test_a_product_a_sweep_deactivated_is_left_behind_as_well(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """Same arrangement as the test above, and that is the point of writing it.

    ``read_priced_products`` filters on ``is_active`` inside the query it
    already runs, so a product withdrawn by an import sweep is missing from the
    answer exactly as a product deleted from the catalog is. The handler must
    not grow a second, looser check against ``product_exists`` — that predicate
    is documented as the same one, and a repeat that disagreed with it would
    put a line in the cart that checkout then refuses.
    """
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (make_priced_product_view(1),)

    view = await repeat_order_handler.handle(repeat(order))

    assert view.skipped_product_names == (SECOND_PRODUCT_NAME,)
    assert quantities(cart_gateway) == {"1c-product-1": 2}


async def test_a_product_this_price_list_no_longer_covers_is_left_behind(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """A product shown as "price on request" browses fine and buys not at all.

    It is also the one of the three that arrives as a row rather than as an
    absence, so a handler that only checked for missing rows would carry this
    line into the cart, where it would sit unpriced and hide the checkout
    button with nothing on screen explaining why.
    """
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2, price=None),
    )

    view = await repeat_order_handler.handle(repeat(order))

    assert view.moved_line_count == 1
    assert view.skipped_product_names == (SECOND_PRODUCT_NAME,)
    assert quantities(cart_gateway) == {"1c-product-1": 2}


async def test_an_order_nothing_of_which_still_sells_moves_nothing(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """A refusal would be wrong here: nothing failed, the assortment moved on.

    The screen this lands on says so and offers the catalog, which is the only
    useful next step. Reporting it as an error would put "something went wrong"
    in front of somebody whose order was simply a year old.
    """
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = ()

    view = await repeat_order_handler.handle(repeat(order))

    assert view.moved_nothing
    assert view.skipped_product_names == ("Товар 1", SECOND_PRODUCT_NAME)
    assert cart_gateway.carts[customer.id].is_empty


async def test_what_was_already_in_the_cart_stays_where_it_was(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """The merge, in one assertion: product 3 survives, product 1 is set.

    Product 1 is in both the cart and the order, and the cart ends up with the
    order's two rather than with the seven somebody had chosen or with nine.
    Adding would make the button dangerous to press twice; leaving it alone
    would make "repeat this order" not repeat it.
    """
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, {1: 7, 3: 4})
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    view = await repeat_order_handler.handle(repeat(order))

    assert view.moved_line_count == 2
    assert view.line_count == 3
    assert quantities(cart_gateway) == {
        "1c-product-1": 2,
        "1c-product-2": 3,
        "1c-product-3": 4,
    }


async def test_repeating_twice_leaves_the_cart_the_first_one_left(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """The property that makes this safe on a button two screens from the cart.

    ``AddToCartCommand`` is deliberately not idempotent, because a double tap
    on a product card is visible on that card and undone by the button beside
    it. Here a double tap would double ten quantities at once, and the person
    would find out at the till.
    """
    customer = await seed_user()
    acting_as(customer.id)
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    await repeat_order_handler.handle(repeat(order))
    await repeat_order_handler.handle(repeat(order))

    assert quantities(cart_gateway) == {"1c-product-1": 2, "1c-product-2": 3}


async def test_a_cart_with_no_room_left_refuses_instead_of_filling_up(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """The ceiling is the cart's rule and is left to the cart to enforce.

    Restating it in the handler would give it a second home, and dropping the
    lines that did not fit would be a repeat that quietly produced a different
    order. The refusal reaches the person as "the cart is full", and
    ``TransactionPipeline`` rolls back whatever the loop managed first, so the
    cart they come back to is the cart they left.
    """
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, dict.fromkeys(range(10, 10 + MAX_CART_LINES), 1))
    order = seed_order(customer.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    with pytest.raises(CartLineLimitExceededError):
        await repeat_order_handler.handle(repeat(order))


async def test_somebody_elses_order_cannot_be_repeated(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    pricing_gateway: StubPricingGateway,
    cart_gateway: InMemoryCartCommandGateway,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    """``IsOrderOwner`` and nothing else, checked before anything is written.

    An order identifier is a UUID somebody could in principle supply, and what
    it would otherwise buy them is a copy of another customer's shopping list —
    including which products a wholesale buyer takes and in what quantities.

    The refusal comes before the catalog is read and before a cart is created,
    so guessing costs the shop nothing either.
    """
    owner = await seed_user(phone_number="+79991112233", external_id="111")
    intruder = await seed_user(phone_number="+79994445566", external_id="222")
    acting_as(intruder.id)
    seed_order(owner.id, lines=TWO_LINES)
    pricing_gateway.priced_products = (make_priced_product_view(1),)

    with pytest.raises(AuthorizationError):
        await repeat_order_handler.handle(RepeatOrderCommand(order_id=make_order_id()))

    assert cart_gateway.carts == {}
    assert pricing_gateway.asked_for == []


async def test_an_order_that_does_not_exist_is_refused_as_missing(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    repeat_order_handler: RepeatOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)

    with pytest.raises(OrderNotFoundError):
        await repeat_order_handler.handle(RepeatOrderCommand(order_id=make_order_id()))
