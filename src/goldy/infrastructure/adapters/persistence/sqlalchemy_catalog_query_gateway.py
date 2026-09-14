import logging
from collections.abc import Sequence
from typing import Final, override

from sqlalchemy import ColumnElement, Executable, RowMapping, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.catalog import CatalogQueryGateway
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
from goldy.infrastructure.adapters.persistence import (
    catalog_listing_statements as listing,
    catalog_search_statements as search,
)
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.catalog_row_view_mapper import CatalogRowViewMapper
from goldy.infrastructure.persistence.models import (
    catalog_categories_table,
    catalog_prices_table,
    catalog_products_table,
    normalize_name,
    normalize_sku,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyCatalogQueryGateway(CatalogQueryGateway):
    """Read-side DAO over the catalog projection.

    One responsibility: run the storefront's reads and hand the rows to the
    mapper. How a listing is selected, joined, ordered and paged lives in
    ``catalog_listing_statements``; what counts as a search hit and how hits
    are ranked lives in ``catalog_search_statements``. Both are pure functions
    over the tables, which is what keeps every method here to one statement
    and one execution.

    Prices are joined in rather than fetched per row, and stock is summed over
    warehouses in the same statement, so a listing costs one round trip for the
    page and one for its total regardless of how many products are on it.

    **Stock is summed from the first day**, although 1C gives no warehouse
    breakdown yet and the consumer writes a fixed ``'*'``. That is the whole
    point: when real warehouses arrive, neither this SQL nor the port changes.

    The join against the prices is an outer one, and a product with no row
    under this price type comes back unpriced instead of missing. A listing
    that hid such products would hide most of the catalog on the day a price
    list failed to export, and the shop sells to order anyway.

    ``is_active`` is the one predicate that decides whether a product is still
    in the catalog, and it is used identically by :meth:`product_exists` and
    :meth:`read_existing_product_ids`. ``CartQueryGateway`` has to mark a line
    available by exactly the same rule: stricter here and a line vanishes from
    the cart while the screen still shows it as fine, looser and a line marked
    unavailable survives the button meant to clear it.

    :meth:`read_product` is the deliberate exception. A card is opened from an
    order placed last spring as well as from a listing, so it reads a product
    whether or not it is still active and hands the flag to the screen.
    """

    def __init__(
        self,
        session: AsyncSession,
        catalog_row_view_mapper: CatalogRowViewMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._mapper: Final[CatalogRowViewMapper] = catalog_row_view_mapper

    @override
    async def read_root_categories(self) -> Sequence[CategoryView]:
        return await self._categories_where(
            catalog_categories_table.c.parent_id.is_(None),
        )

    @override
    async def read_subcategories(self, parent_id: CategoryId) -> Sequence[CategoryView]:
        return await self._categories_where(
            catalog_categories_table.c.parent_id == parent_id.value,
        )

    @override
    async def read_category(self, category_id: CategoryId) -> CategoryView | None:
        stmt = select(catalog_categories_table).where(
            catalog_categories_table.c.id == category_id.value,
            catalog_categories_table.c.is_active,
        )

        row = await self._row(stmt, "the category")
        return None if row is None else self._mapper.to_category_view(row)

    @override
    async def read_products(
        self,
        *,
        filters: ProductFilters,
        price_type_id: PriceTypeId,
        pagination: Pagination,
        sorting: ProductSorting,
    ) -> ProductListView:
        conditions: list[ColumnElement[bool]] = [catalog_products_table.c.is_active]

        if filters.category_id is not None:
            path = await self._category_path(filters.category_id)

            if path is None:
                return ProductListView(products=(), total=0)

            conditions.append(listing.in_subtree_of(path))

        stmt = listing.paginate(
            listing
            .listing_select(price_type_id)
            .where(*conditions)
            .order_by(*listing.listing_order(sorting)),
            pagination,
        )
        rows = await self._rows(stmt, "the product listing")

        return ProductListView(
            products=[self._mapper.to_product_list_item_view(row) for row in rows],
            total=await self._count(conditions, "the product listing"),
        )

    @override
    async def read_product(
        self,
        product_id: ProductId,
        price_type_id: PriceTypeId,
    ) -> ProductView | None:
        stmt = (
            select(
                catalog_products_table.c.id,
                catalog_products_table.c.sku,
                catalog_products_table.c.name,
                catalog_products_table.c.full_name,
                catalog_products_table.c.category_id,
                catalog_categories_table.c.name.label("category_name"),
                catalog_products_table.c.unit_name,
                catalog_products_table.c.unit_ratio,
                catalog_products_table.c.description,
                catalog_products_table.c.image_url,
                catalog_products_table.c.is_active,
                catalog_prices_table.c.amount,
                catalog_prices_table.c.currency,
                listing.stock_total(),
            )
            .select_from(
                catalog_products_table.outerjoin(
                    catalog_prices_table,
                    listing.price_join(price_type_id),
                ).outerjoin(
                    catalog_categories_table,
                    catalog_categories_table.c.id == catalog_products_table.c.category_id,
                ),
            )
            .where(catalog_products_table.c.id == product_id.value)
        )

        row = await self._row(stmt, "the product card")
        return None if row is None else self._mapper.to_product_view(row)

    @override
    async def product_exists(self, product_id: ProductId) -> bool:
        stmt = select(catalog_products_table.c.id).where(
            catalog_products_table.c.id == product_id.value,
            catalog_products_table.c.is_active,
        )

        return await self._row(stmt, "the product") is not None

    @override
    async def read_existing_product_ids(
        self,
        product_ids: Sequence[ProductId],
    ) -> Sequence[ProductId]:
        if not product_ids:
            return ()

        stmt = select(catalog_products_table.c.id).where(
            catalog_products_table.c.id.in_([
                product_id.value for product_id in product_ids
            ]),
            catalog_products_table.c.is_active,
        )

        rows = await self._rows(stmt, "the existing products")
        return [ProductId(value=row["id"]) for row in rows]

    @override
    async def search_products(
        self,
        *,
        term: SearchTerm,
        price_type_id: PriceTypeId,
        pagination: Pagination,
    ) -> ProductSearchView:
        typed = term.value.strip()
        sku_term = normalize_sku(typed)
        name_term = normalize_name(typed)
        conditions = [
            catalog_products_table.c.is_active,
            search.search_match(sku_term, name_term),
        ]

        stmt = listing.paginate(
            listing
            .listing_select(price_type_id)
            .where(*conditions)
            .order_by(*search.search_ranking(sku_term, name_term)),
            pagination,
        )
        rows = await self._rows(stmt, "the search results")

        return ProductSearchView(
            products=[self._mapper.to_product_list_item_view(row) for row in rows],
            total=await self._count(conditions, "the search results"),
            exact_sku_product_id=await self._only_product_with_sku(sku_term),
        )

    async def _categories_where(
        self,
        condition: ColumnElement[bool],
    ) -> Sequence[CategoryView]:
        stmt = (
            select(catalog_categories_table)
            .where(catalog_categories_table.c.is_active, condition)
            .order_by(catalog_categories_table.c.name, catalog_categories_table.c.id)
        )

        rows = await self._rows(stmt, "the category level")
        return [self._mapper.to_category_view(row) for row in rows]

    async def _only_product_with_sku(self, sku_term: str) -> str | None:
        """The one product this article names, when it names exactly one.

        Two rows are fetched rather than one so that "exactly one" can be told
        from "the first of several". Any other number is a list, and that holds
        whether or not the shop keeps its articles unique — 1C does not make
        it.
        """
        stmt = (
            select(catalog_products_table.c.id)
            .where(
                catalog_products_table.c.is_active,
                catalog_products_table.c.sku_normalized == sku_term,
            )
            .limit(2)
        )

        rows = await self._rows(stmt, "the exact article match")
        return rows[0]["id"] if len(rows) == 1 else None

    async def _category_path(self, category_id: CategoryId) -> str | None:
        """The path of a group, or nothing when the group no longer exists.

        ``None`` means the group was swept between the screen being drawn and
        the button being tapped. That is an ordinary consequence of an import,
        and the caller answers it with an empty page rather than a refusal.
        """
        stmt = select(catalog_categories_table.c.path).where(
            catalog_categories_table.c.id == category_id.value,
            catalog_categories_table.c.is_active,
        )

        row = await self._row(stmt, "the category path")
        return None if row is None else str(row["path"])

    async def _count(self, conditions: Sequence[ColumnElement[bool]], what: str) -> int:
        stmt = select(func.count()).select_from(catalog_products_table).where(*conditions)

        try:
            return (await self._session.execute(stmt)).scalar_one()
        except SQLAlchemyError as e:
            logger.exception("failed to count %s", what)
            msg = f"Failed to count {what}."
            raise RepoError(msg) from e

    async def _rows(self, stmt: Executable, what: str) -> Sequence[RowMapping]:
        try:
            return (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read %s", what)
            msg = f"Failed to read {what}."
            raise RepoError(msg) from e

    async def _row(self, stmt: Executable, what: str) -> RowMapping | None:
        try:
            return (await self._session.execute(stmt)).mappings().one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read %s", what)
            msg = f"Failed to read {what}."
            raise RepoError(msg) from e
