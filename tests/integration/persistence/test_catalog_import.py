"""Filling the catalog projection from 1C, and emptying it of what left.

Everything here is a property of the SQL rather than of a handler, which is why
none of it can be shown without a database. The upsert is unconditional: what
1C sends on a run is the current state of 1C, so a row dated earlier than the
one stored is a price rolled back, not a stale delivery, and it has to win. The
sweep selects by ``batch_id``, and what it does to the rows it selects differs
by scope: products are deactivated and kept forever because placed orders point
at them, while prices are deleted, because a price the shop no longer offers
that survives in the projection is money lost directly.

Imports run through the command rather than through the gateway, because the
handler is what decides which collections of a snapshot are written and which
price rows are refused before a customer can see them.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from dishka import FromDishka
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncEngine

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.ports.catalog import (
    CatalogQueryGateway,
    CatalogScopeKind,
    CatalogSnapshot,
)
from goldy.application.common.query_params.catalog_filters import (
    ProductFilters,
    ProductSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.views.catalog import ProductListView
from tests.integration.arrange import CommandSender
from tests.integration.inject import inject
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    SOURCE_CHANGED_AT,
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_scope,
    make_snapshot,
)
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    make_price_type_id,
    make_product_id,
)

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

SECOND_BATCH_ID: str = "batch-0002"
RETAIL_PRICE_TYPE_ID: str = "1c-price-type-retail"
LATER: datetime = SOURCE_CHANGED_AT.replace(year=SOURCE_CHANGED_AT.year + 1)
"""A price set a year after the one the factories date theirs with."""


@inject
async def test_the_whole_catalog_imported_twice_looks_imported_once(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """Every run of the exchange sends the whole reference again.

    The second run carries a batch id of its own, so nothing about it is a
    repeat as far as the sweep is concerned — and the projection still has to
    come out with the same rows and the same values rather than with doubles.
    """
    await send_worker_command(ImportCatalogCommand(snapshot=_a_full_catalog(BATCH_ID)))

    await send_worker_command(
        ImportCatalogCommand(snapshot=_a_full_catalog(SECOND_BATCH_ID)),
    )

    listing = await _listing(catalog)
    assert listing.total == 2
    assert [product.id for product in listing.products] == [
        make_product_id(1).value,
        make_product_id(2).value,
    ]
    assert [product.name for product in listing.products] == ["Product 1", "Product 2"]


@inject
async def test_a_price_1c_rolled_back_to_an_earlier_date_is_written_as_sent(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
    engine: AsyncEngine,
) -> None:
    """Unposting a price document in 1C revives the price before it, dated earlier.

    The register slice then hands the export that earlier record, and it is
    the current state of 1C, so the projection has to take it as sent. The
    upsert used to refuse a row dated before the stored one: the stored row
    then kept its old batch id, the finalisation swept it as absent, and the
    product stood without a price until the next run inserted it afresh.
    """
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                products=(make_product_row(1),),
                price_types=(make_price_type_row(),),
                prices=(make_price_row(1, amount="120.00", source_changed_at=LATER),),
            ),
        ),
    )

    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                prices=(make_price_row(1, amount="100.00"),),
            ),
        ),
    )
    finalized = await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        ),
    )

    stored = await _stored_price(engine)
    listing = await _listing(catalog)
    assert finalized.swept == 0
    assert stored.amount == Decimal("100.00")
    assert stored.source_changed_at == SOURCE_CHANGED_AT
    assert stored.batch_id == SECOND_BATCH_ID
    assert listing.products[0].unit_price is not None
    assert listing.products[0].unit_price.amount == Decimal("100.00")


@inject
async def test_a_product_the_next_run_never_mentioned_leaves_the_storefront(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """What 1C stopped exporting stops being sold, without the row going away.

    Deactivated rather than deleted, because an order placed last spring points
    at it and its card is expected to still open in the customer's history.
    """
    await send_worker_command(ImportCatalogCommand(snapshot=_a_full_catalog(BATCH_ID)))
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                products=(make_product_row(1),),
            ),
        ),
    )

    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRODUCTS),
        ),
    )

    listing = await _listing(catalog)
    assert [product.id for product in listing.products] == [make_product_id(1).value]
    assert not await catalog.product_exists(make_product_id(2))

    withdrawn = await catalog.read_product(make_product_id(2), make_price_type_id())
    assert withdrawn is not None
    assert withdrawn.is_active is False


@inject
async def test_a_price_the_next_run_never_mentioned_is_deleted(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """A price the shop no longer offers must not survive the export that dropped it."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_full_catalog(BATCH_ID)))
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                prices=(make_price_row(1),),
            ),
        ),
    )

    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        ),
    )

    listing = await _listing(catalog)
    priced = {product.id: product.unit_price for product in listing.products}
    assert priced[make_product_id(1).value] is not None
    assert priced[make_product_id(2).value] is None


@inject
async def test_exporting_one_price_list_leaves_the_others_alone(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """The scope is not decoration: without it the sweep wipes the whole table.

    A wholesale export mentions no retail price at all, so "whatever this batch
    did not mention is gone" is only true inside the price list it was about.
    """
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                products=(make_product_row(1),),
                price_types=(
                    make_price_type_row(),
                    make_price_type_row(RETAIL_PRICE_TYPE_ID),
                ),
                prices=(
                    make_price_row(1, amount="100.00"),
                    make_price_row(
                        1,
                        amount="150.00",
                        price_type_id=RETAIL_PRICE_TYPE_ID,
                    ),
                ),
            ),
        ),
    )

    await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        ),
    )

    wholesale = await _listing(catalog)
    retail = await _listing(catalog, price_type_id=RETAIL_PRICE_TYPE_ID)
    assert wholesale.products[0].unit_price is None
    assert retail.products[0].unit_price is not None
    assert retail.products[0].unit_price.amount == Decimal("150.00")


@inject
async def test_a_price_list_that_vanished_takes_its_prices_with_it(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """The price sweep never reaches a list the exchange stopped sending.

    It is scoped to the list a batch was about, and no batch is ever about a
    list that is gone — the first live run against 1C left the seed catalog's
    prices behind exactly this way. Sweeping the price types is the one moment
    the projection learns that a list vanished, so that is where its prices go.
    """
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                products=(make_product_row(1),),
                price_types=(
                    make_price_type_row(),
                    make_price_type_row(RETAIL_PRICE_TYPE_ID),
                ),
                prices=(
                    make_price_row(1, amount="100.00"),
                    make_price_row(
                        1,
                        amount="150.00",
                        price_type_id=RETAIL_PRICE_TYPE_ID,
                    ),
                ),
            ),
        ),
    )
    await send_worker_command(
        ImportCatalogCommand(
            snapshot=make_snapshot(
                batch_id=SECOND_BATCH_ID,
                price_types=(make_price_type_row(),),
            ),
        ),
    )

    finalized = await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRICE_TYPES),
        ),
    )

    wholesale = await _listing(catalog)
    retail = await _listing(catalog, price_type_id=RETAIL_PRICE_TYPE_ID)
    assert finalized.swept == 1
    assert wholesale.products[0].unit_price is not None
    assert retail.products[0].unit_price is None


@inject
async def test_a_run_that_changed_nothing_sweeps_nothing(
    send_worker_command: CommandSender,
    catalog: FromDishka[CatalogQueryGateway],
) -> None:
    """The idempotence that matters: the second run must not empty the shop."""
    await send_worker_command(ImportCatalogCommand(snapshot=_a_full_catalog(BATCH_ID)))
    await send_worker_command(
        ImportCatalogCommand(snapshot=_a_full_catalog(SECOND_BATCH_ID)),
    )

    finalized = await send_worker_command(
        FinalizeCatalogImportCommand(
            batch_id=SECOND_BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRODUCTS),
        ),
    )

    listing = await _listing(catalog)
    assert finalized.swept == 0
    assert listing.total == 2


def _a_full_catalog(batch_id: str) -> CatalogSnapshot:
    """Everything a run of the exchange carries, stamped with one batch id."""
    return make_snapshot(
        batch_id=batch_id,
        products=(make_product_row(1), make_product_row(2)),
        price_types=(make_price_type_row(),),
        prices=(make_price_row(1), make_price_row(2)),
    )


async def _stored_price(engine: AsyncEngine) -> Row[tuple[Decimal, datetime, str]]:
    """Product 1's wholesale price as the table holds it, columns the views hide.

    Read with SQL rather than through the gateway because the assertion is
    about ``source_changed_at`` and ``batch_id``, and no view carries either.
    """
    statement = text(
        "SELECT amount, source_changed_at, batch_id FROM catalog_prices "
        "WHERE product_id = :product_id AND price_type_id = :price_type_id",
    ).bindparams(product_id=make_product_id(1).value, price_type_id=PRICE_TYPE_ID)

    async with engine.connect() as connection:
        return (await connection.execute(statement)).one()


async def _listing(
    catalog: CatalogQueryGateway,
    price_type_id: str = PRICE_TYPE_ID,
) -> ProductListView:
    return await catalog.read_products(
        filters=ProductFilters(),
        price_type_id=make_price_type_id(price_type_id),
        pagination=Pagination(),
        sorting=ProductSorting(),
    )
