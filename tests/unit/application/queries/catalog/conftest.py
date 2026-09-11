"""The catalog query handlers, assembled from the catalog stubs."""

import pytest

from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.queries.catalog.get_product.handler import GetProductHandler
from goldy.application.queries.catalog.list_categories.handler import (
    ListCategoriesHandler,
)
from goldy.application.queries.catalog.list_products.handler import ListProductsHandler
from goldy.application.queries.catalog.search_products.handler import (
    SearchProductsHandler,
)
from tests.unit.factories.catalog_factories import make_price_type_view
from tests.unit.stubs.catalog import StubCatalogQueryGateway, StubPricingGateway
from tests.unit.stubs.identity import StubIdentityProvider


@pytest.fixture()
def catalog_query_gateway() -> StubCatalogQueryGateway:
    return StubCatalogQueryGateway()


@pytest.fixture()
def pricing_gateway() -> StubPricingGateway:
    """Resolves to a supported price list — a test about refusal overrides it."""
    return StubPricingGateway(make_price_type_view())


@pytest.fixture()
def price_type_provider(
    identity_provider: StubIdentityProvider,
    pricing_gateway: StubPricingGateway,
) -> PriceTypeProvider:
    return PriceTypeProvider(identity_provider, pricing_gateway)


@pytest.fixture()
def list_categories_handler(
    catalog_query_gateway: StubCatalogQueryGateway,
) -> ListCategoriesHandler:
    return ListCategoriesHandler(catalog_query_gateway)


@pytest.fixture()
def list_products_handler(
    price_type_provider: PriceTypeProvider,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> ListProductsHandler:
    return ListProductsHandler(price_type_provider, catalog_query_gateway)


@pytest.fixture()
def get_product_handler(
    price_type_provider: PriceTypeProvider,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> GetProductHandler:
    return GetProductHandler(price_type_provider, catalog_query_gateway)


@pytest.fixture()
def search_products_handler(
    price_type_provider: PriceTypeProvider,
    catalog_query_gateway: StubCatalogQueryGateway,
) -> SearchProductsHandler:
    return SearchProductsHandler(price_type_provider, catalog_query_gateway)
