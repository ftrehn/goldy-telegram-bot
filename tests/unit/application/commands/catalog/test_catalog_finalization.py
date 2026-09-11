import pytest

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.finalize_catalog_import.handler import (
    FinalizeCatalogImportHandler,
)
from goldy.application.common.ports.catalog import CatalogScopeKind
from goldy.application.error import CatalogSnapshotError
from tests.unit.factories.catalog_factories import BATCH_ID, WAREHOUSE_ID, make_scope
from tests.unit.factories.shop_factories import PRICE_TYPE_ID
from tests.unit.stubs.catalog import RecordingCatalogProjectionGateway


async def test_a_sweep_is_asked_for_by_batch_and_by_scope(
    projection_gateway: RecordingCatalogProjectionGateway,
    finalize_catalog_import_handler: FinalizeCatalogImportHandler,
) -> None:
    """Without the scope, exporting one price list would delete the others."""
    projection_gateway.swept = 3
    scope = make_scope(CatalogScopeKind.PRICES, price_type_id=PRICE_TYPE_ID)

    response = await finalize_catalog_import_handler.handle(
        FinalizeCatalogImportCommand(batch_id=BATCH_ID, scope=scope),
    )

    assert projection_gateway.finalized == [(scope, BATCH_ID)]
    assert response.swept == 3
    assert response.scope == f"prices:{PRICE_TYPE_ID}"


async def test_an_import_that_swept_away_the_default_price_list_is_refused(
    finalize_catalog_import_handler: FinalizeCatalogImportHandler,
) -> None:
    """Whoever ran the import gets the refusal.

    The alternative is the first customer to open the catalog being told there
    are no prices at all.
    """
    command = FinalizeCatalogImportCommand(
        batch_id=BATCH_ID,
        scope=make_scope(CatalogScopeKind.PRICE_TYPES),
    )

    with pytest.raises(CatalogSnapshotError):
        await finalize_catalog_import_handler.handle(command)


async def test_a_price_type_sweep_that_kept_the_default_goes_through(
    projection_gateway: RecordingCatalogProjectionGateway,
    finalize_catalog_import_handler: FinalizeCatalogImportHandler,
) -> None:
    projection_gateway.present_price_types.add(PRICE_TYPE_ID)

    response = await finalize_catalog_import_handler.handle(
        FinalizeCatalogImportCommand(
            batch_id=BATCH_ID,
            scope=make_scope(CatalogScopeKind.PRICE_TYPES),
        ),
    )

    assert response.scope == "price_types"


async def test_finalising_stock_says_nothing_about_price_lists(
    projection_gateway: RecordingCatalogProjectionGateway,
    finalize_catalog_import_handler: FinalizeCatalogImportHandler,
) -> None:
    """Scopes arrive in whatever order the exchange sends them.

    A stock import must not fail because the price lists have not arrived yet.
    """
    response = await finalize_catalog_import_handler.handle(
        FinalizeCatalogImportCommand(
            batch_id=BATCH_ID,
            scope=make_scope(CatalogScopeKind.STOCK, warehouse_id=WAREHOUSE_ID),
        ),
    )

    assert response.scope == f"stock:{WAREHOUSE_ID}"
    assert projection_gateway.present_price_types == set()
