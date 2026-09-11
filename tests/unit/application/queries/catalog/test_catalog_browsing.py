import pytest

from goldy.application.common.query_params.catalog_filters import ProductSortField
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.catalog import ProductListView
from goldy.application.error import (
    PriceTypeNotConfiguredError,
    ProductNotFoundError,
    UnsupportedPriceTypeError,
)
from goldy.application.queries.catalog.get_product.handler import GetProductHandler
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.application.queries.catalog.list_categories.handler import (
    ListCategoriesHandler,
)
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.application.queries.catalog.list_products.handler import ListProductsHandler
from goldy.application.queries.catalog.list_products.query import ListProductsQuery
from tests.unit.application.conftest import ActingAs
from tests.unit.factories.catalog_factories import (
    make_category_id,
    make_category_view,
    make_price_type_view,
    make_product_id_value,
    make_product_list_item,
    make_product_view,
)
from tests.unit.factories.domain_factories import make_user_id
from tests.unit.factories.shop_factories import PRICE_TYPE_ID
from tests.unit.stubs.catalog import StubCatalogQueryGateway, StubPricingGateway


async def test_the_top_of_the_catalog_has_no_heading(
    catalog_query_gateway: StubCatalogQueryGateway,
    list_categories_handler: ListCategoriesHandler,
) -> None:
    catalog_query_gateway.children[None] = (make_category_view(1),)

    view = await list_categories_handler.handle(ListCategoriesQuery())

    assert view.is_root_level
    assert [category.id for category in view.categories] == [make_category_id(1)]


async def test_a_group_comes_back_with_the_group_it_was_opened_from(
    catalog_query_gateway: StubCatalogQueryGateway,
    list_categories_handler: ListCategoriesHandler,
) -> None:
    """The screen draws a heading and its buttons from one read, not two."""
    parent = make_category_view(1)
    catalog_query_gateway.categories[parent.id] = parent
    catalog_query_gateway.children[parent.id] = (make_category_view(2, parent_index=1),)

    view = await list_categories_handler.handle(
        ListCategoriesQuery(parent_id=parent.id),
    )

    assert view.parent == parent
    assert view.has_subgroups
    assert view.categories[0].depth == 1


async def test_a_group_swept_away_by_an_import_is_an_empty_screen(
    list_categories_handler: ListCategoriesHandler,
) -> None:
    """Deactivating a category is a routine consequence of an import.

    A customer who tapped a button one second too late is owed a screen rather
    than a refusal.
    """
    view = await list_categories_handler.handle(
        ListCategoriesQuery(parent_id=make_category_id(9)),
    )

    assert view.parent is None
    assert not view.has_subgroups


async def test_a_listing_is_priced_for_the_customer_asking(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    acting_as(make_user_id())
    catalog_query_gateway.listing = ProductListView(
        products=(make_product_list_item(1),),
        total=1,
    )

    view = await list_products_handler.handle(ListProductsQuery())

    assert view.total == 1
    assert catalog_query_gateway.products_reads[0].price_type_id.value == PRICE_TYPE_ID


async def test_a_listing_of_a_group_carries_that_group_into_the_filters(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    """Which is all the handler can do about the subtree.

    Expanding the path mask is the projection's job and needs its denormalised
    column.
    """
    acting_as(make_user_id())

    await list_products_handler.handle(
        ListProductsQuery(category_id=make_category_id(3)),
    )

    filters = catalog_query_gateway.products_reads[0].filters
    assert filters.category_id is not None
    assert filters.category_id.value == make_category_id(3)


async def test_a_listing_pages_and_orders_where_the_rows_are(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    acting_as(make_user_id())

    await list_products_handler.handle(
        ListProductsQuery(
            limit=5,
            offset=10,
            sort_by=ProductSortField.PRICE,
            order=SortingOrder.DESC,
        ),
    )

    read = catalog_query_gateway.products_reads[0]
    assert (read.pagination.limit, read.pagination.offset) == (5, 10)
    assert read.sorting.sort_by is ProductSortField.PRICE
    assert read.sorting.order is SortingOrder.DESC


async def test_a_listing_defaults_to_names_ascending(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    """A catalog that opened on the cheapest item would be ranking itself."""
    acting_as(make_user_id())

    await list_products_handler.handle(ListProductsQuery())

    sorting = catalog_query_gateway.products_reads[0].sorting
    assert sorting.sort_by is ProductSortField.NAME
    assert sorting.order is SortingOrder.ASC


async def test_a_customer_with_no_price_list_at_all_is_refused(
    acting_as: ActingAs,
    pricing_gateway: StubPricingGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    """No binding and no configured default means a broken import.

    Showing an unpriced catalog instead would hide that from everyone.
    """
    acting_as(make_user_id())
    pricing_gateway.price_type = None

    with pytest.raises(PriceTypeNotConfiguredError):
        await list_products_handler.handle(ListProductsQuery())


async def test_a_price_list_in_an_unknown_currency_is_refused(
    acting_as: ActingAs,
    pricing_gateway: StubPricingGateway,
    list_products_handler: ListProductsHandler,
) -> None:
    """Falling back to the default list is deliberately not an option.

    It would show this customer somebody else's prices without ever saying so.
    """
    acting_as(make_user_id())
    pricing_gateway.price_type = make_price_type_view(is_supported=False)

    with pytest.raises(UnsupportedPriceTypeError):
        await list_products_handler.handle(ListProductsQuery())


async def test_a_card_is_read_under_the_customers_price_list(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    get_product_handler: GetProductHandler,
) -> None:
    acting_as(make_user_id())
    product = make_product_view(1)
    catalog_query_gateway.products[product.id] = product

    view = await get_product_handler.handle(GetProductQuery(product_id=product.id))

    assert view == product
    assert catalog_query_gateway.product_reads[0][1].value == PRICE_TYPE_ID


async def test_a_card_with_no_price_still_opens(
    acting_as: ActingAs,
    catalog_query_gateway: StubCatalogQueryGateway,
    get_product_handler: GetProductHandler,
) -> None:
    """A price on request is a state to browse in; only ordering is impossible."""
    acting_as(make_user_id())
    product = make_product_view(1, price=None)
    catalog_query_gateway.products[product.id] = product

    view = await get_product_handler.handle(GetProductQuery(product_id=product.id))

    assert not view.is_priced


async def test_a_card_the_catalog_no_longer_holds_is_refused(
    acting_as: ActingAs,
    get_product_handler: GetProductHandler,
) -> None:
    acting_as(make_user_id())
    query = GetProductQuery(product_id=make_product_id_value(404))

    with pytest.raises(ProductNotFoundError):
        await get_product_handler.handle(query)
