"""Two people looking at one product and seeing different numbers.

The binding lives in the catalog projection, keyed by phone number, and is
joined at read time — so "which price list" is answered again on every screen
rather than stored anywhere on the customer. The persistence tests already show
the join resolves. What they cannot show is that the number it resolves is the
number the customer is eventually charged, because between the two lie a card, a
cart, a confirmation screen and a snapshot taken onto an order line.
"""

from decimal import Decimal

import pytest

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from tests.integration.scenarios.acting import (
    ActingSender,
    CatalogPublisher,
    OrderPlacer,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import (
    RETAIL_PRICES,
    RETAIL_PRICE_TYPE_ID,
    SECOND_BATCH_ID,
    WHOLESALE_PRICES,
    a_shop,
)
from tests.unit.factories.catalog_factories import (
    make_binding_row,
    make_product_id_value,
)
from tests.unit.factories.shop_factories import PRICE_TYPE_ID

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

BOUND_PHONE: str = "+79995551111"


async def test_two_customers_pay_the_prices_their_own_list_names(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """The card, the cart and the order line, for both of them at once.

    Asserting the card alone would pass with the order priced from the default
    list, which is the failure worth catching: the snapshot is taken by a
    different collaborator than the one the storefront reads through.
    """
    await publish_catalog(
        a_shop(
            bindings=(
                make_binding_row(
                    phone_number=BOUND_PHONE,
                    price_type_id=RETAIL_PRICE_TYPE_ID,
                ),
            ),
        ),
    )

    unbound = await register_shopper()
    bound = await register_shopper(BOUND_PHONE)

    unbound_card = await act(unbound, GetProductQuery(make_product_id_value(1)))
    bound_card = await act(bound, GetProductQuery(make_product_id_value(1)))

    assert unbound_card.unit_price is not None
    assert bound_card.unit_price is not None
    assert unbound_card.unit_price.amount == Decimal(WHOLESALE_PRICES[1])
    assert bound_card.unit_price.amount == Decimal(RETAIL_PRICES[1])

    unbound_order = await act(
        unbound,
        GetOrderQuery(order_id=(await place_order(unbound, {1: 2})).order_id),
    )
    bound_order = await act(
        bound,
        GetOrderQuery(order_id=(await place_order(bound, {1: 2})).order_id),
    )

    assert unbound_order.price_type_id == PRICE_TYPE_ID
    assert bound_order.price_type_id == RETAIL_PRICE_TYPE_ID
    assert unbound_order.total.amount == Decimal(WHOLESALE_PRICES[1]) * 2
    assert bound_order.total.amount == Decimal(RETAIL_PRICES[1]) * 2


async def test_a_customer_1c_never_mentioned_is_charged_the_configured_list(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """No binding is the ordinary state of a new customer, not a failure.

    Worth its own test rather than being read off the one above, because the
    fallback is what every customer of a shop that has not exported a single
    binding depends on — and it is resolved by a ``coalesce`` in the same
    statement, which is exactly the kind of thing that survives being deleted.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    placed = await place_order(customer, {2: 3})

    order = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert order.price_type_id == PRICE_TYPE_ID
    assert order.lines[0].unit_price.amount == Decimal(WHOLESALE_PRICES[2])
    assert order.total.amount == Decimal(WHOLESALE_PRICES[2]) * 3


async def test_a_binding_arriving_from_1c_reprices_a_cart_already_standing(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """The reason the cart stores no prices of its own.

    A customer fills a cart, 1C moves them onto another price list overnight,
    and the cart they come back to is worth what the new list says. Had the
    cart kept the prices it was filled at, the customer would be invoiced
    against numbers the shop no longer offers, and nothing would ever correct
    them — nobody re-reads a cart line.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper(BOUND_PHONE)

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))
    before = await act(customer, GetCartQuery())
    assert before.total.amount == Decimal(WHOLESALE_PRICES[1])

    await publish_catalog(
        a_shop(
            batch_id=SECOND_BATCH_ID,
            bindings=(
                make_binding_row(
                    phone_number=BOUND_PHONE,
                    price_type_id=RETAIL_PRICE_TYPE_ID,
                ),
            ),
        ),
    )

    after = await act(customer, GetCartQuery())
    assert after.total.amount == Decimal(RETAIL_PRICES[1])
