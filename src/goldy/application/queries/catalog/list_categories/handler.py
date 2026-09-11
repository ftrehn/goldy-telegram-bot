from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.views.catalog import CategoryListView
from goldy.application.queries.catalog.list_categories.query import ListCategoriesQuery
from goldy.domain.catalog.values.category_id import CategoryId


class ListCategoriesHandler(QueryHandler[ListCategoriesQuery, CategoryListView]):
    """Reads one level of the tree, plus the group it hangs under.

    No price type and no access rule, unlike every other catalog query. A group
    carries no price, so resolving the customer's price list would be a second
    round trip for nothing; and there is no rule about who may see which group
    — the storefront is one storefront, and the auth gate has already turned
    away anyone unregistered or blocked.

    The heading is read here rather than by a second query because the screen
    needs both halves to render once. It costs one lookup by primary key, and
    the alternative is a dialog that fires two requests where one would do.
    """

    def __init__(self, catalog_query_gateway: CatalogQueryGateway) -> None:
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway

    @override
    async def handle(self, query: ListCategoriesQuery) -> CategoryListView:
        parent_id = None if query.parent_id is None else CategoryId(value=query.parent_id)
        parent = (
            None
            if parent_id is None
            else await self._catalog_query_gateway.read_category(parent_id)
        )
        categories = await self._catalog_query_gateway.read_categories(parent_id)

        return CategoryListView(parent=parent, categories=tuple(categories))
