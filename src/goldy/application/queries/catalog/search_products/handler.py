from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.search_term import SearchTerm
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.views.catalog import ProductSearchView
from goldy.application.queries.catalog.search_products.query import SearchProductsQuery


class SearchProductsHandler(QueryHandler[SearchProductsQuery, ProductSearchView]):
    """Runs a search and hands back a page of it, ranked by the projection.

    Ranking is not done here and cannot be: it is three steps of SQL — an exact
    match on the normalised article, then the full-text rank, then trigram
    similarity — over rows this handler never sees. Telling an article from a
    name is knowledge of the 1C format, and it lives where the columns do.

    Length is the one thing this layer checks, and it checks it by building a
    ``SearchTerm``: a term of one character cannot use the trigram index and
    would turn into a sequential scan over the whole catalog. An empty result
    is not an error — it is a screen of its own, with the query still on it.
    """

    def __init__(
        self,
        price_type_provider: PriceTypeProvider,
        catalog_query_gateway: CatalogQueryGateway,
    ) -> None:
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway

    @override
    async def handle(self, query: SearchProductsQuery) -> ProductSearchView:
        term = SearchTerm(value=query.term)
        price_type_id = await self._price_type_provider.current()

        return await self._catalog_query_gateway.search_products(
            term=term,
            price_type_id=price_type_id,
            pagination=Pagination(limit=query.limit, offset=query.offset),
        )
