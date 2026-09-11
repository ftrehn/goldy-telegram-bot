"""Stand-ins for the three catalog ports.

The read-side stubs answer with whatever a test put in them and record what
they were asked, because that is where the interesting decisions of a catalog
handler are: which price type it resolved, which filters it built, and which
page it asked for. Filtering in Python here would only reimplement the SQL
these ports exist to hide, and then test the reimplementation.

The projection stub is a recorder for the same reason. Whether an upsert
refuses a stale row is decided by a SQL condition in the adapter, so a stub
that reimplemented it would prove nothing about the handler that calls it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import final, override

from goldy.application.common.ports.catalog import (
    CatalogProjectionGateway,
    CatalogQueryGateway,
    CatalogScope,
    CategoryRow,
    PriceRow,
    PriceTypeBindingRow,
    PriceTypeRow,
    PricingGateway,
    ProductRow,
    StockRow,
)
from goldy.application.common.query_params.catalog_filters import (
    ProductFilters,
    ProductSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.search_term import SearchTerm
from goldy.application.common.views.catalog import (
    CategoryView,
    PriceTypeView,
    PricedProductView,
    ProductListView,
    ProductSearchView,
    ProductView,
)
from goldy.domain.catalog.values.category_id import CategoryId
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.users.values.user_id import UserId


@dataclass(frozen=True, slots=True)
class ProductsRead:
    """One call to ``read_products``, kept whole so a test can name any part."""

    filters: ProductFilters
    price_type_id: PriceTypeId
    pagination: Pagination
    sorting: ProductSorting


@dataclass(frozen=True, slots=True)
class SearchRead:
    """One call to ``search_products``."""

    term: SearchTerm
    price_type_id: PriceTypeId
    pagination: Pagination


@final
class StubCatalogQueryGateway(CatalogQueryGateway):
    """Answers storefront reads from dictionaries a test filled in."""

    def __init__(self) -> None:
        self.categories: dict[str, CategoryView] = {}
        self.children: dict[str | None, tuple[CategoryView, ...]] = {}
        self.products: dict[str, ProductView] = {}
        self.listing: ProductListView = ProductListView(products=(), total=0)
        self.search_result: ProductSearchView = ProductSearchView(
            products=(),
            total=0,
            exact_sku_product_id=None,
        )
        self.products_reads: list[ProductsRead] = []
        self.search_reads: list[SearchRead] = []
        self.product_reads: list[tuple[ProductId, PriceTypeId]] = []

    @override
    async def read_categories(
        self,
        parent_id: CategoryId | None,
    ) -> Sequence[CategoryView]:
        return self.children.get(None if parent_id is None else parent_id.value, ())

    @override
    async def read_category(self, category_id: CategoryId) -> CategoryView | None:
        return self.categories.get(category_id.value)

    @override
    async def read_products(
        self,
        *,
        filters: ProductFilters,
        price_type_id: PriceTypeId,
        pagination: Pagination,
        sorting: ProductSorting,
    ) -> ProductListView:
        self.products_reads.append(
            ProductsRead(
                filters=filters,
                price_type_id=price_type_id,
                pagination=pagination,
                sorting=sorting,
            ),
        )
        return self.listing

    @override
    async def read_product(
        self,
        product_id: ProductId,
        price_type_id: PriceTypeId,
    ) -> ProductView | None:
        self.product_reads.append((product_id, price_type_id))
        return self.products.get(product_id.value)

    @override
    async def product_exists(self, product_id: ProductId) -> bool:
        return product_id.value in self.products

    @override
    async def read_existing_product_ids(
        self,
        product_ids: Sequence[ProductId],
    ) -> Sequence[ProductId]:
        return tuple(
            product_id for product_id in product_ids if product_id.value in self.products
        )

    @override
    async def search_products(
        self,
        *,
        term: SearchTerm,
        price_type_id: PriceTypeId,
        pagination: Pagination,
    ) -> ProductSearchView:
        self.search_reads.append(
            SearchRead(term=term, price_type_id=price_type_id, pagination=pagination),
        )
        return self.search_result


@final
class StubPricingGateway(PricingGateway):
    """Hands back the price type and the priced products a test chose."""

    def __init__(self, price_type: PriceTypeView | None = None) -> None:
        self.price_type: PriceTypeView | None = price_type
        self.priced_products: tuple[PricedProductView, ...] = ()
        self.asked_for: list[UserId] = []

    @override
    async def read_price_type_for(self, user_id: UserId) -> PriceTypeView | None:
        self.asked_for.append(user_id)
        return self.price_type

    @override
    async def read_priced_products(
        self,
        product_ids: Sequence[ProductId],
        price_type_id: PriceTypeId,
    ) -> Sequence[PricedProductView]:
        wanted = {product_id.value for product_id in product_ids}
        return tuple(
            priced for priced in self.priced_products if priced.product_id in wanted
        )


@final
class RecordingCatalogProjectionGateway(CatalogProjectionGateway):
    """Keeps every row it was handed, together with the batch it came in.

    Each upsert reports the number of rows it was given, which is what the
    production adapter reports for a batch nothing in the projection is newer
    than — the ordinary case, and the only one a handler can be written for.
    """

    def __init__(self) -> None:
        self.categories: list[CategoryRow] = []
        self.products: list[ProductRow] = []
        self.price_types: list[PriceTypeRow] = []
        self.prices: list[PriceRow] = []
        self.stock: list[StockRow] = []
        self.bindings: list[PriceTypeBindingRow] = []
        self.batch_ids: list[str] = []
        self.finalized: list[tuple[CatalogScope, str]] = []
        self.swept: int = 0
        self.present_price_types: set[str] = set()

    @override
    async def upsert_categories(
        self,
        categories: Sequence[CategoryRow],
        batch_id: str,
    ) -> int:
        self.categories.extend(categories)
        self.batch_ids.append(batch_id)
        return len(categories)

    @override
    async def upsert_products(
        self,
        products: Sequence[ProductRow],
        batch_id: str,
    ) -> int:
        self.products.extend(products)
        self.batch_ids.append(batch_id)
        return len(products)

    @override
    async def upsert_price_types(
        self,
        price_types: Sequence[PriceTypeRow],
        batch_id: str,
    ) -> int:
        self.price_types.extend(price_types)
        self.batch_ids.append(batch_id)
        self.present_price_types.update(row.id for row in price_types)
        return len(price_types)

    @override
    async def upsert_prices(self, prices: Sequence[PriceRow], batch_id: str) -> int:
        self.prices.extend(prices)
        self.batch_ids.append(batch_id)
        return len(prices)

    @override
    async def upsert_stock(self, stock: Sequence[StockRow], batch_id: str) -> int:
        self.stock.extend(stock)
        self.batch_ids.append(batch_id)
        return len(stock)

    @override
    async def upsert_price_type_bindings(
        self,
        bindings: Sequence[PriceTypeBindingRow],
        batch_id: str,
    ) -> int:
        self.bindings.extend(bindings)
        self.batch_ids.append(batch_id)
        return len(bindings)

    @override
    async def finalize(self, scope: CatalogScope, batch_id: str) -> int:
        self.finalized.append((scope, batch_id))
        return self.swept

    @override
    async def has_price_type(self, price_type_id: PriceTypeId) -> bool:
        return price_type_id.value in self.present_price_types
