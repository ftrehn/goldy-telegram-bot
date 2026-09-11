import pytest

from goldy.application.common.views.catalog import ProductSearchView
from goldy.application.error import SearchTermError
from goldy.application.queries.catalog.search_products.handler import (
    SearchProductsHandler,
)
from goldy.application.queries.catalog.search_products.query import SearchProductsQuery
from tests.unit.application.conftest import ActingAs
from tests.unit.factories.catalog_factories import (
    make_product_id_value,
    make_product_list_item,
)
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.factories.shop_factories import PRICE_TYPE_ID
from tests.unit.stubs.catalog import StubCatalogQueryGateway

TYPED: str = "AB-123"


async def test_a_search_reaches_the_projection_exactly_as_it_was_typed(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    search_products_handler: SearchProductsHandler,
) -> None:
    """Normalisation is not this layer's business.

    Folding ``AB-123`` and ``ab123`` together has to agree with the generated
    columns, so it happens where those columns are.
    """
    acting_as(make_user_id())

    await search_products_handler.handle(
        SearchProductsQuery(term=TYPED, limit=5, offset=5),
    )

    read = catalog_query_gateway.search_reads[0]
    assert read.term.value == TYPED
    assert read.price_type_id.value == PRICE_TYPE_ID
    assert (read.pagination.limit, read.pagination.offset) == (5, 5)


async def test_a_term_too_short_to_index_never_reaches_the_catalog(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    search_products_handler: SearchProductsHandler,
) -> None:
    """One character cannot use the trigram index.

    The query would degrade into a sequential scan of the whole catalog.
    """
    acting_as(make_user_id())

    with pytest.raises(SearchTermError):
        await search_products_handler.handle(SearchProductsQuery(term="a"))

    assert catalog_query_gateway.search_reads == []


async def test_finding_nothing_is_an_answer_and_not_a_failure(
    acting_as: ActingAs,
    search_products_handler: SearchProductsHandler,
) -> None:
    acting_as(make_user_id())

    view = await search_products_handler.handle(SearchProductsQuery(term=TYPED))

    assert view.is_empty
    assert view.total == 0


async def test_one_exact_article_is_carried_through_as_a_shortcut(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    search_products_handler: SearchProductsHandler,
) -> None:
    """Deciding that a term matched one article is a comparison over a column.

    Which is why the answer arrives together with the results.
    """
    acting_as(make_user_id())
    catalog_query_gateway.search_result = ProductSearchView(
        products=(make_product_list_item(7),),
        total=1,
        exact_sku_product_id=make_product_id_value(7),
    )

    view = await search_products_handler.handle(SearchProductsQuery(term=TYPED))

    assert view.exact_sku_product_id == make_product_id_value(7)
