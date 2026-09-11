from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.query_params.catalog_filters import ProductSortField
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.catalog import ProductListView


@dataclass(frozen=True, slots=True)
class ListProductsQuery(Query[ProductListView]):
    """One page of a listing, priced for whoever is asking.

    ``category_id`` selects the whole subtree below that group rather than the
    group itself. Products in 1C sit in the leaves of the hierarchy, so a
    listing restricted to one node would show an empty screen under every group
    that has subgroups — which is most of them.

    Sorted by name ascending by default. Sorting by price is offered as a
    choice and not as the default, because a listing that opens on the cheapest
    item ranks the shop's own catalog for it.

    Search is a separate query rather than a term on this one: the two order
    their results by entirely different rules, and one handler switching
    between them would take a ``category_id`` it could not use.
    """

    category_id: str | None = None
    limit: int | None = None
    offset: int | None = None
    sort_by: ProductSortField = ProductSortField.NAME
    order: SortingOrder = SortingOrder.ASC
