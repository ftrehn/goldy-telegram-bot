"""The catalog query handlers, assembled from the catalog stubs."""

import pytest

from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.queries.catalog.get_product.handler import GetProductHandler
from goldy.application.queries.catalog.list_categories.handler import (
    ListCategoriesHandler,
)
from goldy.application.queries.catalog.list_products.handler import ListProductsHandler
from goldy.application.queries.catalog.search_products.handler import (
    SearchProductsHandler,
)
from tests.unit.factories.catalog_factories import make_resolved_price_type
from tests.unit.stubs.catalog import StubCatalogQueryGateway, StubPricingReader
from tests.unit.stubs.identity import StubIdentityProvider


@pytest.fixture()
def catalog_query_gateway() -> StubCatalogQueryGateway:
    return StubCatalogQueryGateway()


@pytest.fixture()
def pricing_reader() -> StubPricingReader:
    """Resolves to a supported price list — a test about refusal overrides it."""
    return StubPricingReader(make_resolved_price_type())


@pytest.fixture()
def price_type_resolver(pricing_reader: StubPricingReader) -> PriceTypeResolver:
    return PriceTypeResolver(pricing_reader)


@pytest.fixture()
def list_categories_handler(
    catalog_query_gateway: StubCatalogQueryGateway,
) -> ListCategoriesHandler:
    return ListCategoriesHandler(catalog_query_gateway)


@pytest.fixture()
def list_products_handler(
    identity_provider: StubIdentityProvider,
    price_type_resolver: PriceTypeResolver,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> ListProductsHandler:
    return ListProductsHandler(
        identity_provider,
        price_type_resolver,
        catalog_query_gateway,
    )


@pytest.fixture()
def get_product_handler(
    identity_provider: StubIdentityProvider,
    price_type_resolver: PriceTypeResolver,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> GetProductHandler:
    return GetProductHandler(
        identity_provider, price_type_resolver, catalog_query_gateway
    )


@pytest.fixture()
def search_products_handler(
    identity_provider: StubIdentityProvider,
    price_type_resolver: PriceTypeResolver,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> SearchProductsHandler:
    return SearchProductsHandler(
        identity_provider,
        price_type_resolver,
        catalog_query_gateway,
    )
