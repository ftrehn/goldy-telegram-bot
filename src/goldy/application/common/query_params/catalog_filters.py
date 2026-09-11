from dataclasses import dataclass
from enum import StrEnum

from goldy.application.common.query_params.sorting import SortingOrder
from goldy.domain.catalog.values.category_id import CategoryId


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductFilters:
    """Narrows a storefront listing. Unset means "the whole catalog".

    Only the category, and deliberately nothing else. Neither stock nor the
    presence of a price may ever narrow a listing: the shop sells to order and
    a product with no price under this customer's price type is shown as
    "price on request". A filter for either would be the first step towards
    refusing orders the shop can actually fill.

    The category selects a whole subtree rather than one node, because products
    in 1C sit in the leaves: a listing restricted to one node shows an empty
    group wherever that group has subgroups.
    """

    category_id: CategoryId | None = None


class ProductSortField(StrEnum):
    """What a storefront listing is ordered by.

    Search results are not ordered by either of these. Ranking there is three
    steps of SQL — exact article match, then full-text rank, then trigram
    similarity — which is an ordering over the projection rather than a choice
    the caller gets to make, and it is why search is a separate query instead
    of a flag on this one.
    """

    NAME = "name"
    PRICE = "price"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductSorting:
    """How a storefront listing is ordered.

    Both halves belong to the gateway rather than to a handler. A page is
    twenty products out of thousands, and ordering a page that has already been
    fetched is not ordering the catalog — sorting by price in Python would
    quietly reorder twenty rows and call it a sort.
    """

    sort_by: ProductSortField = ProductSortField.NAME
    order: SortingOrder = SortingOrder.ASC
