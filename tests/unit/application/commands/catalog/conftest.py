"""The two catalog import handlers, over one recording projection."""

import pytest

from goldy.application.commands.catalog.finalize_catalog_import.handler import (
    FinalizeCatalogImportHandler,
)
from goldy.application.commands.catalog.import_catalog.handler import (
    ImportCatalogHandler,
)
from tests.unit.factories.shop_factories import make_price_type_id
from tests.unit.stubs.catalog import RecordingCatalogProjectionGateway


@pytest.fixture()
def projection_gateway() -> RecordingCatalogProjectionGateway:
    return RecordingCatalogProjectionGateway()


@pytest.fixture()
def import_catalog_handler(
    projection_gateway: RecordingCatalogProjectionGateway,
) -> ImportCatalogHandler:
    return ImportCatalogHandler(projection_gateway)


@pytest.fixture()
def finalize_catalog_import_handler(
    projection_gateway: RecordingCatalogProjectionGateway,
) -> FinalizeCatalogImportHandler:
    """Configured with the same default price type the fixtures import."""
    return FinalizeCatalogImportHandler(projection_gateway, make_price_type_id())
