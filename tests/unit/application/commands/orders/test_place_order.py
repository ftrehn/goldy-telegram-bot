"""Placing an order: the prices, the screen it was confirmed on, the cart."""

from decimal import Decimal

import pytest

from goldy.application.commands.orders.place_order.command import PlaceOrderCommand
from goldy.application.commands.orders.place_order.handler import PlaceOrderHandler
from goldy.application.error import (
    CartRepricedError,
    PriceTypeNotConfiguredError,
    ProductNotPricedError,
    UnsupportedPriceTypeError,
)
from goldy.domain.carts.errors import EmptyCartError
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.errors import UnpricedCartLineError
from goldy.domain.orders.events import OrderPlaced
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.factories.catalog_factories import make_price_type_view
from tests.unit.factories.domain_factories import CUSTOMER_PHONE
from tests.unit.factories.order_factories import make_priced_product_view
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    PRICE_TYPE_ID,
    RECIPIENT_FIRST_NAME,
    RECIPIENT_LAST_NAME,
)
from tests.unit.stubs.catalog import StubPricingGateway
from tests.unit.stubs.generators import StubOrderNumberGenerator
from tests.unit.stubs.orders import InMemoryOrderCommandGateway

from .conftest import CartSeeder

TWO_LINES_TOTAL: str = "59.97"
CART: dict[int, int] = {1: 2, 2: 1}


def place_order(
    total: str = TWO_LINES_TOTAL,
    line_count: int = 2,
    comment: str | None = None,
    address: str = DELIVERY_ADDRESS,
) -> PlaceOrderCommand:
    """The command as the confirmation screen assembles it."""
    return PlaceOrderCommand(
        delivery_address=address,
        recipient_first_name=RECIPIENT_FIRST_NAME,
        recipient_last_name=RECIPIENT_LAST_NAME,
        recipient_phone_number=CUSTOMER_PHONE,
        comment=comment,
        expected_total=Decimal(total),
        expected_line_count=line_count,
    )


async def test_the_cart_becomes_an_order_at_the_prices_just_read(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_gateway: InMemoryOrderCommandGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    cart = seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    view = await place_order_handler.handle(place_order())

    order = order_gateway.orders[order_gateway.added[0]]
    assert view.order_number == order.number.value
    assert order.customer_id == customer.id
    assert order.price_type_id.value == PRICE_TYPE_ID
    assert order.total.amount == Decimal(TWO_LINES_TOTAL)
    assert [line.position for line in order.lines] == [1, 2]
    assert cart.is_empty


async def test_the_order_records_that_it_was_placed(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    events_collection: EventsCollection,
    place_order_handler: PlaceOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    await place_order_handler.handle(place_order())

    placed = [
        event
        for event in events_collection.pull_events()
        if isinstance(event, OrderPlaced)
    ]
    assert len(placed) == 1
    assert placed[0].total_amount == TWO_LINES_TOTAL
    assert placed[0].line_count == 2


async def test_a_total_that_moved_since_the_screen_refuses_the_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_gateway: InMemoryOrderCommandGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """Charging more than was shown is the one way this shop looks dishonest."""
    customer = await seed_user()
    acting_as(customer.id)
    cart = seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1, price="29.99"),
        make_priced_product_view(2),
    )

    with pytest.raises(CartRepricedError):
        await place_order_handler.handle(place_order())

    assert order_gateway.added == []
    assert not cart.is_empty


async def test_a_line_count_that_moved_since_the_screen_refuses_the_order(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_gateway: InMemoryOrderCommandGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    with pytest.raises(CartRepricedError):
        await place_order_handler.handle(place_order(line_count=3))

    assert order_gateway.added == []


async def test_a_price_that_did_not_move_is_not_a_repricing(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_gateway: InMemoryOrderCommandGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """The screen prints ``59.97``; the same number written ``59.970`` is it."""
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )

    await place_order_handler.handle(place_order(total="59.970"))

    assert len(order_gateway.added) == 1


async def test_a_second_confirmation_tap_meets_an_empty_cart(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_gateway: InMemoryOrderCommandGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """The real backstop against a double tap.

    It is also the reason the emptying belongs to checkout rather than to the
    handler.

    The second command still carries the totals of the screen, so the order the
    two checks are made in is what decides which error the dialog gets: an
    empty cart has to be told apart from a cart that was repriced.
    """
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (
        make_priced_product_view(1),
        make_priced_product_view(2),
    )
    await place_order_handler.handle(place_order())

    with pytest.raises(EmptyCartError):
        await place_order_handler.handle(place_order())

    assert len(order_gateway.added) == 1


async def test_a_product_that_left_the_catalog_names_the_line(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    order_number_generator: StubOrderNumberGenerator,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """A vanished product is not a repricing, and must not be reported as one."""
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, CART)
    pricing_gateway.priced_products = (make_priced_product_view(1),)

    with pytest.raises(UnpricedCartLineError):
        await place_order_handler.handle(place_order())

    assert order_number_generator.calls == 0


async def test_a_product_shown_as_price_on_request_cannot_be_ordered(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, {1: 1})
    pricing_gateway.priced_products = (make_priced_product_view(1, price=None),)

    with pytest.raises(ProductNotPricedError):
        await place_order_handler.handle(place_order(line_count=1))


async def test_a_shop_with_no_price_list_at_all_refuses(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, {1: 1})
    pricing_gateway.price_type = None

    with pytest.raises(PriceTypeNotConfiguredError):
        await place_order_handler.handle(place_order(line_count=1))


async def test_a_price_list_in_an_unknown_currency_refuses(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_cart: CartSeeder,
    pricing_gateway: StubPricingGateway,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """Falling back to the default list here would show somebody else's prices."""
    customer = await seed_user()
    acting_as(customer.id)
    seed_cart(customer.id, {1: 1})
    pricing_gateway.price_type = make_price_type_view(is_supported=False)

    with pytest.raises(UnsupportedPriceTypeError):
        await place_order_handler.handle(place_order(line_count=1))


async def test_an_empty_cart_is_refused_before_anything_is_minted(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_number_generator: StubOrderNumberGenerator,
    place_order_handler: PlaceOrderHandler,
) -> None:
    """Somebody who never added anything has no cart row at all.

    ``ensure_for`` creating one on the spot must not turn that into an order.
    """
    customer = await seed_user()
    acting_as(customer.id)

    with pytest.raises(EmptyCartError):
        await place_order_handler.handle(place_order())

    assert order_number_generator.calls == 0
