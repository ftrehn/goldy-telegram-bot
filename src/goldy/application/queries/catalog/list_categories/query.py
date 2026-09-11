from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.catalog import CategoryListView


@dataclass(frozen=True, slots=True)
class ListCategoriesQuery(Query[CategoryListView]):
    """One level of the catalog tree: the subgroups of a group, or the roots.

    Only the immediate children, never the whole subtree. The category screen
    draws its subgroups as buttons and lists the products of the entire subtree
    underneath them, so a deeper read would be rows nobody renders.

    ``parent_id`` is the identifier 1C knows the group by, carried as text
    because that is what it is — the query is built from a callback payload and
    has no business constructing a domain value out of it.
    """

    parent_id: str | None = None
