"""The catalog moving while somebody is shopping in it.

A cart lives for days and the projection is re-imported every few minutes, so
"the shop changed between two taps" is the ordinary case rather than the edge
one. Each of the three ways it can change has its own refusal, and they are
deliberately not the same refusal: a product withdrawn, a price moved and a
price withdrawn need three different things said to the customer, and collapsing
any two of them would mean telling somebody "ask a manager about the price"
about a product the shop has stopped selling.

What must never happen is the fourth outcome — an order quietly placed at the
price the screen was drawn with half an hour ago.
"""

from decimal import Decimal

import pytest

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.commands.carts.remove_unavailable_cart_lines.command import (
    RemoveUnavailableCartLinesCommand,
)
from goldy.application.common.ports.catalog import CatalogScopeKind
from goldy.application.error import (
    CartRepricedError,
    ProductNotFoundError,
    ProductNotPricedError,
)
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.domain.orders.errors import UnpricedCartLineError
from tests.integration.scenarios.acting import (
    ActingSender,
    CatalogPublisher,
    CatalogSweeper,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import (
    SECOND_BATCH_ID,
    WHOLESALE_PRICES,
    a_checkout,
    a_shop,
)
from tests.unit.factories.catalog_factories import make_product_id_value, make_scope
from tests.unit.factories.shop_factories import PRICE_TYPE_ID

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

RAISED_PRICE: str = "120.00"


async def test_a_product_withdrawn_after_it_was_added_blocks_the_order(
    publish_catalog: CatalogPublisher,
    sweep_catalog: CatalogSweeper,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """The line stays on the screen, marked, and checkout refuses until it goes.

    The cart is read through a ``LEFT JOIN`` taken without an ``is_active``
    filter precisely so this can happen: with the filter the line would vanish
    and the total would quietly shrink, and nobody notices something that is
    not there.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))
    await act(customer, AddToCartCommand(product_id=make_product_id_value(2)))

    await publish_catalog(a_shop(batch_id=SECOND_BATCH_ID, products=(1,)))
    await sweep_catalog(SECOND_BATCH_ID, make_scope())

    cart = await act(customer, GetCartQuery())
    assert cart.line_count == 2
    assert cart.has_unavailable_lines is True

    with pytest.raises(UnpricedCartLineError):
        await act(customer, a_checkout(cart))

    assert (await act(customer, ListMyOrdersQuery())).total == 0

    await act(customer, RemoveUnavailableCartLinesCommand())

    tidied = await act(customer, GetCartQuery())
    assert tidied.line_count == 1
    assert tidied.has_unavailable_lines is False

    placed = await act(customer, a_checkout(tidied))
    order = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert [line.product_id for line in order.lines] == [make_product_id_value(1)]


async def test_a_product_withdrawn_before_it_was_added_cannot_be_added(
    publish_catalog: CatalogPublisher,
    sweep_catalog: CatalogSweeper,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """The one moment a vanished product can be caught before it becomes a line.

    A listing drawn a second before the sweep still has the button on it, and
    the tap arrives afterwards.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await publish_catalog(a_shop(batch_id=SECOND_BATCH_ID, products=(1,)))
    await sweep_catalog(SECOND_BATCH_ID, make_scope())

    with pytest.raises(ProductNotFoundError):
        await act(customer, AddToCartCommand(product_id=make_product_id_value(2)))

    assert (await act(customer, GetCartQuery())).is_empty


async def test_a_price_that_moved_between_the_screen_and_the_button_is_refused(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """The customer is charged what they were shown, or not charged at all.

    The gap here is not seconds. Somebody walks away from the confirmation
    screen to look up an address and comes back half an hour later, by which
    time the exchange has run twice. Charging more than was shown is the one
    way this shop could look dishonest, so the order is refused and the screen
    is redrawn — and the redrawn screen is what the second attempt agrees with.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1), quantity=2))
    shown = await act(customer, GetCartQuery())
    assert shown.total.amount == Decimal(WHOLESALE_PRICES[1]) * 2

    await publish_catalog(
        a_shop(batch_id=SECOND_BATCH_ID, wholesale={1: RAISED_PRICE}),
    )

    with pytest.raises(CartRepricedError):
        await act(customer, a_checkout(shown))

    assert (await act(customer, ListMyOrdersQuery())).total == 0

    redrawn = await act(customer, GetCartQuery())
    assert redrawn.total.amount == Decimal(RAISED_PRICE) * 2

    placed = await act(customer, a_checkout(redrawn))
    order = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert order.total.amount == Decimal(RAISED_PRICE) * 2


async def test_a_product_that_lost_its_price_cannot_be_ordered_at_the_old_one(
    publish_catalog: CatalogPublisher,
    sweep_catalog: CatalogSweeper,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """Still in the catalog, no longer priced — a third state, told apart.

    Prices are deleted by a sweep rather than deactivated, because a price the
    shop has withdrawn that survives in the projection is money lost directly.
    The customer is left looking at "price on request", which is a fine state
    to browse in and an impossible one to order from.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))

    await publish_catalog(
        a_shop(batch_id=SECOND_BATCH_ID, wholesale={2: WHOLESALE_PRICES[2]}),
    )
    await sweep_catalog(
        SECOND_BATCH_ID,
        make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
    )

    cart = await act(customer, GetCartQuery())
    assert cart.has_unavailable_lines is False
    assert cart.has_unpriced_lines is True
    assert cart.lines[0].unit_price is None

    with pytest.raises(ProductNotPricedError):
        await act(customer, a_checkout(cart))

    assert (await act(customer, ListMyOrdersQuery())).total == 0
