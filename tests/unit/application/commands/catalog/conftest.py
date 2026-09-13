"""The two catalog import handlers, over one recording projection."""

import pytest

from goldy.application.commands.catalog.finalize_catalog_import.handler import (
    FinalizeCatalogImportHandler,
)
from goldy.application.commands.catalog.import_catalog.handler import (
    ImportCatalogHandler,
)
from tests.unit.factories.shop_factories import make_price_type_id
from tests.unit.stubs.catalog import RecordingCatalogProjectionDao


@pytest.fixture()
def projection_dao() -> RecordingCatalogProjectionDao:
    return RecordingCatalogProjectionDao()


@pytest.fixture()
def import_catalog_handler(
    projection_dao: RecordingCatalogProjectionDao,
) -> ImportCatalogHandler:
    return ImportCatalogHandler(projection_dao)


@pytest.fixture()
def finalize_catalog_import_handler(
    projection_dao: RecordingCatalogProjectionDao,
) -> FinalizeCatalogImportHandler:
    """Configured with the same default price type the fixtures import."""
    return FinalizeCatalogImportHandler(projection_dao, make_price_type_id())
