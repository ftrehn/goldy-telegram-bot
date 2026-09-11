from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.commands.catalog.import_catalog.handler import (
    ImportCatalogHandler,
)
from goldy.application.common.ports.catalog import CatalogScopeKind
from tests.unit.factories.catalog_factories import (
    BATCH_ID,
    WAREHOUSE_ID,
    make_binding_row,
    make_category_row,
    make_price_row,
    make_price_type_row,
    make_product_row,
    make_scope,
    make_snapshot,
    make_stock_row,
)
from tests.unit.factories.shop_factories import PRICE_TYPE_ID
from tests.unit.stubs.catalog import RecordingCatalogProjectionGateway


async def test_a_batch_writes_every_kind_it_carries_under_one_mark(
    projection_gateway: RecordingCatalogProjectionGateway,
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """A batch is whatever its sender put in it.

    The file the seeder reads holds the whole catalog at once while a consumer
    message holds one kind, and both are this same call.
    """
    snapshot = make_snapshot(
        categories=(make_category_row(1),),
        products=(make_product_row(1),),
        price_types=(make_price_type_row(),),
        prices=(make_price_row(1),),
        stock=(make_stock_row(1),),
        bindings=(make_binding_row(),),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.accepted == 6
    assert set(projection_gateway.batch_ids) == {BATCH_ID}


async def test_an_empty_batch_writes_nothing_at_all(
    projection_gateway: RecordingCatalogProjectionGateway,
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """Mentioning nothing is not the same as emptying something.

    Emptying is what the finalisation command is for.
    """
    response = await import_catalog_handler.handle(
        ImportCatalogCommand(make_snapshot()),
    )

    assert response.accepted == 0
    assert projection_gateway.batch_ids == []


async def test_a_price_of_zero_never_reaches_a_storefront(
    projection_gateway: RecordingCatalogProjectionGateway,
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """Zero reads as "free" on a screen.

    ``Money`` allows it, so it would reach an order line without a word.
    """
    snapshot = make_snapshot(
        scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        prices=(make_price_row(1, amount="0"), make_price_row(2)),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.accepted == 1
    assert response.discarded == 1
    assert [price.product_id for price in projection_gateway.prices] == [
        make_price_row(2).product_id,
    ]


async def test_a_price_in_an_unknown_currency_is_discarded_rather_than_shown(
    projection_gateway: RecordingCatalogProjectionGateway,
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """Storing it would mean printing somebody's yuan as roubles."""
    snapshot = make_snapshot(
        scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        prices=(make_price_row(1, currency="cny"),),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.discarded == 1
    assert projection_gateway.prices == []


async def test_a_currency_1c_spelled_in_capitals_is_still_our_currency(
    projection_gateway: RecordingCatalogProjectionGateway,
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """The exchange writes the code as 1C has it.

    Refusing on case would throw away a whole price list over its spelling.
    """
    snapshot = make_snapshot(
        scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        prices=(make_price_row(1, currency="RUB"),),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.discarded == 0
    assert len(projection_gateway.prices) == 1


async def test_the_response_names_which_price_list_a_batch_was_about(
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    """An import log saying only "prices" cannot be read afterwards."""
    snapshot = make_snapshot(
        scope=make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID),
        prices=(make_price_row(1),),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.scope == f"prices:{PRICE_TYPE_ID}"
    assert response.batch_id == BATCH_ID


async def test_a_stock_batch_is_named_by_its_warehouse(
    import_catalog_handler: ImportCatalogHandler,
) -> None:
    snapshot = make_snapshot(
        scope=make_scope(CatalogScopeKind.STOCK, warehouse_id=WAREHOUSE_ID),
        stock=(make_stock_row(1),),
    )

    response = await import_catalog_handler.handle(ImportCatalogCommand(snapshot))

    assert response.scope == f"stock:{WAREHOUSE_ID}"
