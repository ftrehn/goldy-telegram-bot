from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.catalog import ProductSearchView


@dataclass(frozen=True, slots=True)
class SearchProductsQuery(Query[ProductSearchView]):
    """One page of search results, across the whole catalog.

    The term travels raw, exactly as it was typed. Folding ``AB-123``,
    ``ab 123`` and ``ab123`` together has to agree character for character with
    the generated columns Postgres computes, so it happens inside the catalog
    gateway; doing it here would put ``infrastructure.persistence.models`` in
    the application layer and fail the layers contract on the first run.

    Never scoped to the open category, and there is deliberately no field for
    one. Search exists chiefly for articles, and somebody typing an article is
    not browsing a group.
    """

    term: str
    limit: int | None = None
    offset: int | None = None
