from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from goldy.application.common.query_params.catalog_filters import (
        ProductFilters,
        ProductSorting,
    )
    from goldy.application.common.query_params.pagination import Pagination
    from goldy.application.common.query_params.search_term import SearchTerm
    from goldy.application.common.views.catalog import (
        CategoryView,
        ProductListView,
        ProductSearchView,
        ProductView,
    )
    from goldy.domain.catalog.values.category_id import CategoryId
    from goldy.domain.catalog.values.price_type_id import PriceTypeId
    from goldy.domain.catalog.values.product_id import ProductId


class CatalogQueryGateway(Protocol):
    """Read-side DAO for the storefront: categories, listings, cards, search.

    Prices are joined in here rather than fetched by a handler. A page is
    twenty products, and pricing them in Python means either twenty reads or
    one bulk read merged by hand — a join written in the wrong language — while
    sorting by price is not expressible at all once the page has been fetched.

    Takes a ``PriceTypeId`` and never a ``UserId``. With a user id the cache key
    would grow one entry per customer, and a catalog DAO would start knowing
    about people.

    A ``Protocol`` for exactly that reason: **these reads may be cached**, and a
    caching decorator over this port has to be invisible to every handler using
    it. Anything read with the intent to write belongs on
    :class:`PricingGateway` instead, which must not be cached.

    No access rules are consulted anywhere behind this port. There is no rule
    about who may see which product — the storefront is one storefront and only
    the prices differ — and the auth gate has already turned away anyone
    unregistered or blocked.
    """

    @abstractmethod
    async def read_categories(
        self,
        parent_id: CategoryId | None,
    ) -> Sequence[CategoryView]:
        """The immediate subgroups of a group, or the roots when given nothing.

        Only one level: the category screen draws its subgroups as buttons and
        lists the products of the whole subtree underneath them.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_category(self, category_id: CategoryId) -> CategoryView | None:
        """One group, for the heading and the breadcrumb of its screen."""
        raise NotImplementedError

    @abstractmethod
    async def read_products(
        self,
        *,
        filters: ProductFilters,
        price_type_id: PriceTypeId,
        pagination: Pagination,
        sorting: ProductSorting,
    ) -> ProductListView:
        """One page of a listing, priced for this price type.

        A category in the filters selects its whole subtree, because products
        in 1C sit in the leaves of the hierarchy.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_product(
        self,
        product_id: ProductId,
        price_type_id: PriceTypeId,
    ) -> ProductView | None:
        """One product card, priced for this price type."""
        raise NotImplementedError

    @abstractmethod
    async def product_exists(self, product_id: ProductId) -> bool:
        """Whether the catalog still holds this product, price aside.

        What "add to cart" checks. The cart stores no prices, so asking for one
        here would mean resolving the customer's price type for an answer
        nothing uses.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_existing_product_ids(
        self,
        product_ids: Sequence[ProductId],
    ) -> Sequence[ProductId]:
        """Which of these products the catalog still holds, in one query.

        The bulk form of :meth:`product_exists`, answering exactly the same
        question and by the same rule — "removing the unavailable lines" from a
        cart of a hundred products must not be a hundred round trips.

        The two predicates have to agree with the one ``CartQueryGateway``
        marks a line available by. If this method were stricter, a line would
        be removed while the screen still showed it as fine; if it were looser,
        a line marked unavailable would survive the button meant to clear it
        and the customer would tap forever.
        """
        raise NotImplementedError

    @abstractmethod
    async def search_products(
        self,
        *,
        term: SearchTerm,
        price_type_id: PriceTypeId,
        pagination: Pagination,
    ) -> ProductSearchView:
        """One page of search results, across the whole catalog.

        Search is never scoped to the open category. It exists chiefly for
        articles, and somebody typing an article is not browsing a group; the
        results screen says so in its heading so nobody has to guess.

        Ranking is three steps of SQL — exact normalised article, then
        full-text rank, then trigram similarity — and belongs to the
        projection. Telling an article from a name is knowledge of the 1C
        format and lives in the same place.
        """
        raise NotImplementedError
