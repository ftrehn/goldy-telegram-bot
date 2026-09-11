"""The whole way through: an empty database, and an order in the queue.

Every layer under this is already tested on its own, and the reason this test
exists anyway is that none of those tests can fail when two of them disagree.
The price the card prints, the price the cart totals, the price copied onto the
order line and the total the manager reads off the queue are computed by four
different pieces of code, and nothing but walking the path asks whether they
agree about one purchase.
"""

from decimal import Decimal

import pytest

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.commands.carts.clear_cart.command import ClearCartCommand
from goldy.application.commands.orders.change_order_status.command import (
    ChangeOrderStatusCommand,
)
from goldy.application.queries.carts.get_cart.query import GetCartQuery
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.application.queries.catalog.list_products.query import ListProductsQuery
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.domain.orders.values.order_status import OrderStatus
from tests.integration.scenarios.acting import (
    ActingSender,
    CatalogPublisher,
    ManagerRegistrar,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import WHOLESALE_PRICES, a_checkout, a_shop
from tests.unit.factories.catalog_factories import make_product_id_value
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    RECIPIENT_FIRST_NAME,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


async def test_a_customer_walks_from_the_catalog_to_a_confirmed_order(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    register_manager: ManagerRegistrar,
    act: ActingSender,
) -> None:
    """One purchase, from the exchange running to the manager confirming it.

    Written as one long test on purpose. Split into eight, each half of it
    would need the previous seven arranged behind it, and the arrangement would
    stop being the thing under test — which is precisely what this is for.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()
    manager = await register_manager()

    root = await act(customer, ListCategoriesQuery())
    assert root.is_root_level
    assert [group.name for group in root.categories] == ["Group 1"]

    listing = await act(customer, ListProductsQuery(category_id=root.categories[0].id))
    assert listing.total == 2

    card = await act(customer, GetProductQuery(product_id=make_product_id_value(1)))
    assert card.unit_price is not None
    assert card.unit_price.amount == Decimal(WHOLESALE_PRICES[1])

    await act(customer, AddToCartCommand(product_id=card.id, quantity=3))
    await act(customer, AddToCartCommand(product_id=make_product_id_value(2)))

    cart = await act(customer, GetCartQuery())
    assert cart.line_count == 2
    assert cart.has_unavailable_lines is False
    assert cart.total.amount == Decimal(WHOLESALE_PRICES[1]) * 3 + Decimal(
        WHOLESALE_PRICES[2],
    )

    placed = await act(customer, a_checkout(cart))

    assert (await act(customer, GetCartQuery())).is_empty

    mine = await act(customer, ListMyOrdersQuery())
    assert [order.number for order in mine.orders] == [placed.order_number]
    assert mine.orders[0].status == OrderStatus.NEW.value
    assert mine.orders[0].total.amount == cart.total.amount

    queue = await act(manager, ListOrdersQuery())
    assert [order.id for order in queue.orders] == [placed.order_id]
    assert queue.orders[0].customer_id == customer.user_id

    await act(
        manager,
        ChangeOrderStatusCommand(
            order_id=placed.order_id,
            status=OrderStatus.CONFIRMED,
        ),
    )

    seen = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert seen.status == OrderStatus.CONFIRMED.value
    assert seen.delivery_address == DELIVERY_ADDRESS
    assert seen.recipient_first_name == RECIPIENT_FIRST_NAME
    assert seen.total.amount == cart.total.amount

    first, second = seen.lines
    assert (first.position, second.position) == (1, 2)
    assert first.name == "Product 1"
    assert first.sku == "SKU-1"
    assert first.quantity == 3
    assert first.unit_price.amount == Decimal(WHOLESALE_PRICES[1])
    assert first.line_total.amount == Decimal(WHOLESALE_PRICES[1]) * 3
    assert second.name == "Product 2"
    assert second.quantity == 1


async def test_the_cart_survives_a_customer_who_walks_away_and_comes_back(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """A cart lives in the database, not in a dialog.

    Every step of a scenario runs in its own request scope, which is what makes
    this worth asserting: the second addition finds the cart the first one
    created rather than making a second, and the ``ensure_for`` upsert behind
    it is the only reason that holds.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))
    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))
    await act(customer, AddToCartCommand(product_id=make_product_id_value(2)))

    cart = await act(customer, GetCartQuery())

    assert cart.line_count == 2
    assert cart.total_quantity == 3
    assert cart.total.amount == Decimal(WHOLESALE_PRICES[1]) * 2 + Decimal(
        WHOLESALE_PRICES[2],
    )


async def test_emptying_a_cart_of_several_products_leaves_nothing_behind(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """Clearing a cart is one delete of many rows, and that is not a detail.

    ``Cart.clear`` is reached from two places — this button, and every single
    checkout, because ``CheckoutService`` empties the cart in the same
    transaction as the insert. Both flush a delete of every line at once, and
    SQLAlchemy sorts the states it is about to delete by their primary key, half
    of which is a ``ProductId``. A cart holding one product never reaches that
    sort, which is exactly why this needs asserting with two.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    await act(customer, AddToCartCommand(product_id=make_product_id_value(1)))
    await act(customer, AddToCartCommand(product_id=make_product_id_value(2)))

    await act(customer, ClearCartCommand())

    assert (await act(customer, GetCartQuery())).is_empty


async def test_a_product_the_shop_has_none_of_is_still_sold_to_order(
    publish_catalog: CatalogPublisher,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
) -> None:
    """Zero stock is a badge, never a refusal — and that is the owner's decision.

    What the bot holds is a projection of 1C with no reservation behind it, so
    refusing on it would turn away orders the shop can fill while still not
    preventing overselling. This test exists to make the decision expensive to
    reverse by accident: anybody who adds an availability check to the cart or
    to checkout will fail here and have to argue with ADR-0002 first.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    listing = await act(customer, ListProductsQuery())
    [to_order] = [
        product for product in listing.products if product.id == make_product_id_value(2)
    ]
    assert to_order.stock == Decimal(0)
    assert to_order.is_in_stock is False

    await act(customer, AddToCartCommand(product_id=to_order.id, quantity=2))

    cart = await act(customer, GetCartQuery())
    assert cart.lines[0].is_in_stock is False
    assert cart.lines[0].is_available is True

    placed = await act(customer, a_checkout(cart))

    order = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert order.status == OrderStatus.NEW.value
    assert order.total.amount == Decimal(WHOLESALE_PRICES[2]) * 2
