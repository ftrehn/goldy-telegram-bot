"""A fake site with one section, the retail price list and no items yet."""

import pytest

from goldy.infrastructure.adapters.catalog.site_catalog_source import (
    SiteCatalogSource,
)
from tests.unit.factories.site_api_factories import (
    make_site_api_client,
    make_site_price_type,
    make_site_section,
)
from tests.unit.stubs.site_api import FakeSiteCatalog

PAGE_SIZE = 2


@pytest.fixture()
def fake_site() -> FakeSiteCatalog:
    site = FakeSiteCatalog()
    site.sections = [make_site_section()]
    site.price_types = [make_site_price_type()]
    return site


@pytest.fixture()
def site_catalog_source(fake_site: FakeSiteCatalog) -> SiteCatalogSource:
    return SiteCatalogSource(make_site_api_client(fake_site), PAGE_SIZE)
