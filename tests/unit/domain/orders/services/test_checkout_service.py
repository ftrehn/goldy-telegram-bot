from decimal import Decimal
from uuid import UUID

import pytest

from goldy.domain.carts.errors import EmptyCartError
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.errors import CurrencyMismatchError
from goldy.domain.common.values.money import Money
from goldy.domain.orders.errors import UnpricedCartLineError
from goldy.domain.orders.services.checkout_service import CheckoutService
from goldy.domain.orders.values.order_status import OrderStatus
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    make_cart,
    make_checkout,
    make_money,
    make_price_type_id,
    make_priced_product,
    make_product_id,
    make_unit,
)
from tests.unit.stubs.generators import FIRST_ORDER_NUMBER, StubOrderNumberGenerator
from tests.unit.support import emitted_event_names


async def test_checkout_turns_the_whole_cart_into_one_order(
    checkout_service: CheckoutService,
    events_collection: EventsCollection,
) -> None:
    cart = make_cart({1: 2, 2: 1})

    order = await checkout_service.checkout(make_checkout(cart))

    assert order.status is OrderStatus.NEW
    assert len(order.lines) == 2
    assert order.customer_id == make_user_id()
    assert emitted_event_names(events_collection) == ["OrderPlaced"]


async def test_the_order_keeps_the_price_and_the_name_it_was_shown(
    checkout_service: CheckoutService,
) -> None:
    """A snapshot, not a reference.

    The catalog is a projection of 1C and will be rewritten by the next import,
    while the order has to keep showing what was agreed.
    """
    cart = make_cart({1: 3})
    priced = make_priced_product(index=1, price="49.50", name="Гвозди 100 мм")

    order = await checkout_service.checkout(
        make_checkout(cart, priced_products=(priced,)),
    )
    line = order.lines[0]

    assert line.name == priced.name
    assert line.sku == priced.sku
    assert line.unit == priced.unit
    assert line.unit_price == make_money("49.50")
    assert line.total == Money(Decimal("148.50"), Currency.RUB)


async def test_the_order_line_keeps_the_unit_the_quantity_is_counted_in(
    checkout_service: CheckoutService,
) -> None:
    """A quantity of 2 without "шт" or "м" beside it tells the customer nothing.

    Reading the unit out of the catalog when the order is shown would restore
    the reference the snapshot exists to avoid.
    """
    cart = make_cart({1: 2})
    priced = make_priced_product(index=1, unit=make_unit("1c-unit-006", "м"))

    order = await checkout_service.checkout(
        make_checkout(cart, priced_products=(priced,)),
    )

    assert order.lines[0].unit == priced.unit


async def test_a_product_1c_gave_no_article_can_still_be_ordered(
    checkout_service: CheckoutService,
) -> None:
    """The article is optional in 1C, and a strict one here would break checkout.

    Not the import — the projection is Core-only and builds no values — but the
    customer's "place order" button, on a product the shop sells perfectly
    well.
    """
    cart = make_cart({1: 1})

    order = await checkout_service.checkout(
        make_checkout(cart, priced_products=(make_priced_product(with_sku=False),)),
    )

    assert order.lines[0].sku is None


async def test_the_lines_are_numbered_from_one_in_the_order_the_cart_held_them(
    checkout_service: CheckoutService,
) -> None:
    """``(order_id, position)`` is the key, the way a 1C tabular part is addressed."""
    cart = make_cart({1: 1, 2: 1, 3: 1})

    order = await checkout_service.checkout(make_checkout(cart))

    assert [line.position for line in order.lines] == [1, 2, 3]
    assert [line.product_id for line in order.lines] == [
        make_product_id(1),
        make_product_id(2),
        make_product_id(3),
    ]


async def test_the_cart_is_emptied_by_the_same_operation(
    checkout_service: CheckoutService,
) -> None:
    """Emptying the cart is half of the same business operation.

    Left to a handler, that half is the one somebody forgets, and the customer
    gets an order with the same cart still sitting on top of it.
    """
    cart = make_cart({1: 1})

    await checkout_service.checkout(make_checkout(cart))

    assert cart.is_empty is True


async def test_an_empty_cart_cannot_be_checked_out(
    checkout_service: CheckoutService,
    order_number_generator: StubOrderNumberGenerator,
) -> None:
    cart = make_cart()

    with pytest.raises(EmptyCartError):
        await checkout_service.checkout(make_checkout(cart))

    assert order_number_generator.calls == 0


async def test_a_product_the_catalog_can_no_longer_price_leaves_the_cart_alone(
    checkout_service: CheckoutService,
    events_collection: EventsCollection,
    order_number_generator: StubOrderNumberGenerator,
) -> None:
    """Nothing is minted or emptied until every line is built.

    The transaction pipeline commits whatever the handler left behind, so a
    half-applied checkout would be committed as cheerfully as a whole one.
    """
    cart = make_cart({1: 1, 2: 1})

    with pytest.raises(UnpricedCartLineError):
        await checkout_service.checkout(
            make_checkout(cart, priced_products=(make_priced_product(index=1),)),
        )

    assert cart.line_count == 2
    assert order_number_generator.calls == 0
    assert emitted_event_names(events_collection) == []


async def test_a_cart_priced_in_two_currencies_leaves_it_alone_as_well(
    checkout_service: CheckoutService,
    events_collection: EventsCollection,
) -> None:
    cart = make_cart({1: 1, 2: 1})
    priced = (
        make_priced_product(index=1, currency=Currency.RUB),
        make_priced_product(index=2, currency=Currency.USD),
    )

    with pytest.raises(CurrencyMismatchError):
        await checkout_service.checkout(make_checkout(cart, priced_products=priced))

    assert cart.line_count == 2
    assert emitted_event_names(events_collection) == []


async def test_the_order_takes_its_number_from_the_generator(
    checkout_service: CheckoutService,
) -> None:
    """Asking a database sequence is I/O, which is why this service is async."""
    order = await checkout_service.checkout(make_checkout(make_cart({1: 1})))

    assert str(order.number) == str(FIRST_ORDER_NUMBER)
    assert order.id == UUID(int=1)


async def test_two_checkouts_get_different_numbers(
    checkout_service: CheckoutService,
) -> None:
    first = await checkout_service.checkout(make_checkout(make_cart({1: 1})))
    second = await checkout_service.checkout(make_checkout(make_cart({2: 1})))

    assert first.number != second.number
    assert first.id != second.id


async def test_the_order_carries_the_delivery_details_it_was_checked_out_with(
    checkout_service: CheckoutService,
) -> None:
    cart = make_cart({1: 1})

    order = await checkout_service.checkout(
        make_checkout(cart, comment="Позвонить за час"),
    )

    assert str(order.delivery_address) == DELIVERY_ADDRESS
    assert str(order.recipient) == "Данил Ковалев, +79991234567"
    assert order.comment is not None
    assert str(order.comment) == "Позвонить за час"


async def test_the_order_records_the_price_type_it_was_priced_by(
    checkout_service: CheckoutService,
) -> None:
    """The snapshot answers "why was it this price" months later.

    The service takes prices from what it was handed and from nothing else, so
    the price type it records is the one those prices were read under.
    """
    cart = make_cart({1: 1})

    order = await checkout_service.checkout(make_checkout(cart))

    assert order.price_type_id == make_price_type_id()
    assert order.total == make_money()
