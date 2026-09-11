import logging
from collections.abc import Sequence
from typing import Final, override

from sqlalchemy import (
    ColumnElement,
    Executable,
    RowMapping,
    Select,
    and_,
    case,
    func,
    nulls_last,
    or_,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.query_params.catalog_filters import (
    ProductFilters,
    ProductSortField,
    ProductSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.search_term import SearchTerm
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.catalog import (
    CategoryView,
    ProductListView,
    ProductSearchView,
    ProductView,
)
from goldy.domain.catalog.values.category_id import CategoryId
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.catalog_row_view_mapper import CatalogRowViewMapper
from goldy.infrastructure.persistence.models import (
    SEARCH_TEXT_CONFIGURATION,
    catalog_categories_table,
    catalog_prices_table,
    catalog_products_table,
    catalog_stock_table,
    normalize_name,
    normalize_sku,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

MIN_TRIGRAM_LENGTH: Final[int] = 3
"""Below this a GIN trigram index cannot be used at all, so the query changes.

Two characters produce no trigram, and a substring match on them would be a
sequential scan of the whole catalog. A prefix match is what is left, and it is
what somebody typing two characters meant anyway.
"""

PATH_SEPARATOR: Final[str] = "/"
"""What ``catalog_categories.path`` joins its identifiers with.

The same constant the projection gateway builds a path out of. A subtree is
matched as "the path itself, or the path followed by a separator" rather than
as a bare prefix, because bare prefixes make a group whose id starts with
another group's id a member of it.
"""

LIKE_ESCAPE: Final[str] = "\\"


class SqlAlchemyCatalogQueryGateway(CatalogQueryGateway):
    """Read-side DAO over the catalog projection.

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
    async def read_categories(
        self,
        parent_id: CategoryId | None,
    ) -> Sequence[CategoryView]:
        parent_column = catalog_categories_table.c.parent_id
        condition = (
            parent_column.is_(None)
            if parent_id is None
            else parent_column == parent_id.value
        )

        stmt = (
            select(catalog_categories_table)
            .where(catalog_categories_table.c.is_active, condition)
            .order_by(catalog_categories_table.c.name, catalog_categories_table.c.id)
        )

        rows = await self._rows(stmt, "the category level")
        return [self._mapper.to_category_view(row) for row in rows]

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
        conditions = await self._listing_conditions(filters)

        if conditions is None:
            return ProductListView(products=(), total=0)

        stmt = _paginate(
            _listing_select(price_type_id)
            .where(*conditions)
            .order_by(*_listing_order(sorting)),
            pagination,
        )

        rows = await self._rows(stmt, "the product listing")
        total = await self._count(conditions, "the product listing")

        return ProductListView(
            products=tuple(self._mapper.to_product_list_item_view(row) for row in rows),
            total=total,
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
                _stock_total(),
            )
            .select_from(
                catalog_products_table.outerjoin(
                    catalog_prices_table,
                    _price_join(price_type_id),
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
            _search_match(sku_term, name_term),
        ]

        stmt = _paginate(
            _listing_select(price_type_id)
            .where(*conditions)
            .order_by(*_search_ranking(sku_term, name_term)),
            pagination,
        )

        rows = await self._rows(stmt, "the search results")
        total = await self._count(conditions, "the search results")

        return ProductSearchView(
            products=tuple(self._mapper.to_product_list_item_view(row) for row in rows),
            total=total,
            exact_sku_product_id=await self._only_product_with_sku(sku_term),
        )

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

    async def _listing_conditions(
        self,
        filters: ProductFilters,
    ) -> list[ColumnElement[bool]] | None:
        """The WHERE of a listing, or nothing when the group no longer exists.

        Resolving the group's path costs a lookup by primary key, and it buys a
        pattern bound as a parameter instead of one computed inside the
        statement — which is what lets the btree index on ``path`` be used at
        all, and what lets the ``%`` and ``_`` an identifier may contain be
        escaped before Postgres reads them as wildcards.

        ``None`` means the group was swept between the screen being drawn and
        the button being tapped. That is an ordinary consequence of an import,
        and the caller answers it with an empty page rather than a refusal.
        """
        conditions: list[ColumnElement[bool]] = [catalog_products_table.c.is_active]

        if filters.category_id is None:
            return conditions

        path = await self._category_path(filters.category_id)

        if path is None:
            return None

        prefix = _escape_like(path)
        subtree = select(catalog_categories_table.c.id).where(
            or_(
                catalog_categories_table.c.path == path,
                catalog_categories_table.c.path.like(
                    f"{prefix}{PATH_SEPARATOR}%",
                    escape=LIKE_ESCAPE,
                ),
            ),
        )
        conditions.append(catalog_products_table.c.category_id.in_(subtree))

        return conditions

    async def _category_path(self, category_id: CategoryId) -> str | None:
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


def _stock_total() -> ColumnElement[object]:
    """What is free to sell of this product, across every warehouse.

    A sum rather than a column, from the first day. 1C gives no breakdown yet
    and the consumer writes a fixed warehouse, so today this sums one row —
    which is exactly why real warehouses arriving will change nothing here.
    """
    return (
        select(func.sum(catalog_stock_table.c.quantity))
        .where(catalog_stock_table.c.product_id == catalog_products_table.c.id)
        .correlate(catalog_products_table)
        .scalar_subquery()
        .label("stock")
    )


def _price_join(price_type_id: PriceTypeId) -> ColumnElement[bool]:
    """The price of a product under one price list, if there is one."""
    return and_(
        catalog_prices_table.c.product_id == catalog_products_table.c.id,
        catalog_prices_table.c.price_type_id == price_type_id.value,
    )


def _listing_select(price_type_id: PriceTypeId) -> Select[tuple[object, ...]]:
    """The columns every list of products is built from, priced and stocked."""
    return select(
        catalog_products_table.c.id,
        catalog_products_table.c.sku,
        catalog_products_table.c.name,
        catalog_products_table.c.unit_name,
        catalog_prices_table.c.amount,
        catalog_prices_table.c.currency,
        _stock_total(),
    ).select_from(
        catalog_products_table.outerjoin(
            catalog_prices_table,
            _price_join(price_type_id),
        ),
    )


def _listing_order(sorting: ProductSorting) -> tuple[ColumnElement[object], ...]:
    """How a storefront listing is ordered, with unpriced products last.

    Unpriced last in both directions, and deliberately not "cheapest first"
    when ascending: a product with no row under this price list costs nothing
    knowable, and putting it at the top of a listing sorted by price would
    advertise it as the cheapest thing in the shop.

    The identifier closes the ordering so that paging is stable. Names repeat
    in a catalog, and a page boundary falling between two equal names would
    otherwise show one of them twice and the other never.
    """
    column = (
        catalog_prices_table.c.amount
        if sorting.sort_by is ProductSortField.PRICE
        else catalog_products_table.c.name
    )
    direction = column.desc() if sorting.order is SortingOrder.DESC else column.asc()

    return (nulls_last(direction), catalog_products_table.c.id.asc())


def _search_match(sku_term: str, name_term: str) -> ColumnElement[bool]:
    """What counts as a hit, by two mechanisms that answer two questions.

    A fragment of an article is trigrams and nothing else; morphology of the
    name is a dictionary and nothing else. Both are asked, and the ranking
    decides which of them mattered.

    Under three characters neither index applies and the query degrades to a
    prefix match: a substring match on two characters is a sequential scan of
    the catalog, and somebody typing two characters is typing the start of
    something.
    """
    if len(sku_term) < MIN_TRIGRAM_LENGTH:
        return or_(
            catalog_products_table.c.sku_normalized.like(
                f"{_escape_like(sku_term)}%",
                escape=LIKE_ESCAPE,
            ),
            catalog_products_table.c.name_normalized.like(
                f"{_escape_like(name_term)}%",
                escape=LIKE_ESCAPE,
            ),
        )

    return or_(
        catalog_products_table.c.sku_normalized.like(
            f"%{_escape_like(sku_term)}%",
            escape=LIKE_ESCAPE,
        ),
        catalog_products_table.c.search_vector.op("@@", is_comparison=True)(
            _tsquery(name_term),
        ),
        catalog_products_table.c.name_normalized.op("%", is_comparison=True)(name_term),
    )


def _search_ranking(sku_term: str, name_term: str) -> tuple[ColumnElement[object], ...]:
    """Three steps, in the order a person expects them.

    An exact article first, because somebody who typed one typed it to find
    that product and nothing else. Then the full-text rank, which knows that
    "дрели" is "дрель". Then trigram similarity, which is what finds a name
    with a letter missing from it.

    This is an ordering over the projection and not a business rule, which is
    why it lives here and why search is a separate query rather than a flag on
    the listing: it shares not one step with ordering by name or by price.
    """
    exact_article = case(
        (catalog_products_table.c.sku_normalized == sku_term, 0),
        else_=1,
    )

    return (
        exact_article.asc(),
        func.ts_rank(catalog_products_table.c.search_vector, _tsquery(name_term)).desc(),
        func.similarity(catalog_products_table.c.name_normalized, name_term).desc(),
        catalog_products_table.c.name.asc(),
        catalog_products_table.c.id.asc(),
    )


def _tsquery(name_term: str) -> ColumnElement[object]:
    """The search term as a full-text query, over the same normalised text.

    The generated column is built from the normalised name, so the term has to
    reach ``plainto_tsquery`` normalised too. One normalisation for both
    mechanisms is the only version of this that cannot half-work.
    """
    return func.plainto_tsquery(SEARCH_TEXT_CONFIGURATION, name_term)


def _paginate(
    stmt: Select[tuple[object, ...]], pagination: Pagination
) -> Select[tuple[object, ...]]:
    if pagination.limit is not None:
        stmt = stmt.limit(pagination.limit)
    if pagination.offset is not None:
        stmt = stmt.offset(pagination.offset)

    return stmt


def _escape_like(value: str) -> str:
    """Makes text that is data behave like data inside a ``LIKE`` pattern.

    An identifier from 1C may contain a percent sign or an underscore, and both
    are wildcards to Postgres. Unescaped, a category whose path holds one would
    quietly list a different subtree.
    """
    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    return escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")
