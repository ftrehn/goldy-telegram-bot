from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.query_params.catalog_filters import (
    ProductFilters,
    ProductSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.views.catalog import ProductListView
from goldy.application.queries.catalog.list_products.query import ListProductsQuery
from goldy.domain.catalog.values.category_id import CategoryId


class ListProductsHandler(QueryHandler[ListProductsQuery, ProductListView]):
    """Reads one page of a listing with the prices already joined in.

    Neither the paging nor the ordering is done here, and that is the point of
    handing both to the gateway. A page is twenty products out of thousands:
    ordering rows that have already been fetched would reorder the page instead
    of the catalog, and pricing them in Python would mean twenty reads or a
    join written in the wrong language.

    The total comes back with the page from the same request, because a pager
    that only knows its current slice cannot say how many pages there are.
    """

    def __init__(
        self,
        price_type_provider: PriceTypeProvider,
        catalog_query_gateway: CatalogQueryGateway,
    ) -> None:
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway

    @override
    async def handle(self, query: ListProductsQuery) -> ProductListView:
        price_type_id = await self._price_type_provider.current()
        filters = ProductFilters(
            category_id=(
                None if query.category_id is None else CategoryId(value=query.category_id)
            ),
        )

        return await self._catalog_query_gateway.read_products(
            filters=filters,
            price_type_id=price_type_id,
            pagination=Pagination(limit=query.limit, offset=query.offset),
            sorting=ProductSorting(sort_by=query.sort_by, order=query.order),
        )
