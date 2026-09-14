"""What was agreed stays agreed, however far the catalog moves afterwards.

ADR-0003, made expensive to break. An order line copies the name, the article,
the unit and the price at the moment the customer committed, and reads them back
from itself rather than through ``product_id`` — so the shop can rename a
product, re-article it, double its price and stop selling it altogether, and the
document the customer was invoiced against says what it said in March.

The one field on the line that is *not* a snapshot is ``stock``, and it is not
part of the order at all: the card joins today's stock so a manager deciding
whether to confirm can see what is on the shelf next to what was ordered. That
is why this test compares the snapshot fields by name instead of comparing the
lines whole — the difference is the assertion.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from goldy.application.common.ports.catalog import (
    CatalogSnapshot,
    PriceRow,
    ProductRow,
)
from goldy.application.common.views.order import OrderLineView, OrderView
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from tests.integration.scenarios.acting import (
    ActingSender,
    CatalogPublisher,
    CatalogSweeper,
    OrderPlacer,
    ShopperRegistrar,
)
from tests.integration.scenarios.shop import THIRD_BATCH_ID, WHOLESALE_PRICES, a_shop
from tests.unit.factories.catalog_factories import (
    SOURCE_CHANGED_AT,
    make_price_type_row,
    make_product_id_value,
    make_scope,
    make_snapshot,
)
from tests.unit.factories.shop_factories import PRICE_TYPE_ID

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

LATER: datetime = SOURCE_CHANGED_AT.replace(year=SOURCE_CHANGED_AT.year + 1)
RENAMED: str = "Product 1, as 1C calls it now"
REARTICLED: str = "SKU-1-2027"
MULTIPLIED_PRICE: str = "999.00"


async def test_a_placed_order_ignores_everything_the_catalog_does_next(
    publish_catalog: CatalogPublisher,
    sweep_catalog: CatalogSweeper,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Renamed, re-articled, ten times the price, one of them withdrawn.

    All four at once rather than one per test, because each of them is the same
    claim about the same mechanism and a snapshot that survived three of them
    and not the fourth would be broken in exactly the same way.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    placed = await place_order(customer, {1: 2, 2: 1})
    before = await act(customer, GetOrderQuery(order_id=placed.order_id))
    assert before.total.amount == Decimal(WHOLESALE_PRICES[1]) * 2 + Decimal(
        WHOLESALE_PRICES[2],
    )

    await publish_catalog(_a_catalog_that_moved_on())
    await sweep_catalog(THIRD_BATCH_ID, make_scope())

    after = await act(customer, GetOrderQuery(order_id=placed.order_id))

    assert _agreed(after) == _agreed(before)
    assert after.total == before.total
    assert after.price_type_id == before.price_type_id

    history = await act(customer, ListMyOrdersQuery())
    assert history.orders[0].total == before.total
    assert history.orders[0].line_count == 2


async def test_a_withdrawn_product_still_opens_on_the_card_that_bought_it(
    publish_catalog: CatalogPublisher,
    sweep_catalog: CatalogSweeper,
    register_shopper: ShopperRegistrar,
    act: ActingSender,
    place_order: OrderPlacer,
) -> None:
    """Why the sweep deactivates products instead of deleting them.

    Placed orders point at those rows. Deleting them would either break the
    order or force the snapshot to stop being one, and the customer asking
    "what did I buy last spring" is the person who would find out.
    """
    await publish_catalog(a_shop())
    customer = await register_shopper()

    placed = await place_order(customer, {2: 4})

    await publish_catalog(_a_catalog_that_moved_on())
    await sweep_catalog(THIRD_BATCH_ID, make_scope())

    order = await act(customer, GetOrderQuery(order_id=placed.order_id))
    [line] = order.lines

    assert line.product_id == make_product_id_value(2)
    assert line.name == "Product 2"
    assert line.sku == "SKU-2"
    assert line.quantity == 4
    assert line.unit_price.amount == Decimal(WHOLESALE_PRICES[2])
    assert order.total.amount == Decimal(WHOLESALE_PRICES[2]) * 4


def _agreed(order: OrderView) -> list[tuple[object, ...]]:
    """The part of every line that the order owns, without today's stock."""
    return [_snapshot_of(line) for line in order.lines]


def _snapshot_of(line: OrderLineView) -> tuple[object, ...]:
    return (
        line.position,
        line.product_id,
        line.sku,
        line.name,
        line.unit_name,
        line.quantity,
        line.unit_price,
        line.line_total,
    )


def _a_catalog_that_moved_on() -> CatalogSnapshot:
    """A run of the exchange that changes everything an order line copied.

    Stamped later than the first one because the upsert is conditional on the
    timestamp the source put on the row — a batch that did not move it forward
    would be discarded as a replay, and the test would pass without the catalog
    ever having changed.
    """
    return make_snapshot(
        batch_id=THIRD_BATCH_ID,
        products=(
            ProductRow(
                id=make_product_id_value(1),
                sku=REARTICLED,
                name=RENAMED,
                unit_name="кг",
                source_changed_at=LATER,
            ),
        ),
        price_types=(make_price_type_row(),),
        prices=(
            PriceRow(
                product_id=make_product_id_value(1),
                price_type_id=PRICE_TYPE_ID,
                amount=Decimal(MULTIPLIED_PRICE),
                currency="rub",
                source_changed_at=LATER,
            ),
        ),
    )
