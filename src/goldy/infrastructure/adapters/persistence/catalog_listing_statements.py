"""The SQL a storefront listing is built from, apart from running it.

Pure functions over the projection tables and nothing else: no session, no
mapper, no error handling. ``SqlAlchemyCatalogQueryGateway`` composes these
into statements and executes them, and that split is the point — how a listing
is selected, joined, ordered and paged can be read, tested and changed without
touching the class that talks to the database, and the gateway stays a list of
short methods that each run one statement.
"""

from typing import Final

from sqlalchemy import ColumnElement, Select, and_, func, nulls_last, or_, select

from goldy.application.common.query_params.catalog_filters import (
    ProductSortField,
    ProductSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.infrastructure.persistence.models import (
    catalog_categories_table,
    catalog_prices_table,
    catalog_products_table,
    catalog_stock_table,
)

PATH_SEPARATOR: Final[str] = "/"
"""What ``catalog_categories.path`` joins its identifiers with.

The same constant the projection DAO builds a path out of. A subtree is matched
as "the path itself, or the path followed by a separator" rather than as a bare
prefix, because bare prefixes make a group whose id starts with another group's
id a member of it.
"""

LIKE_ESCAPE: Final[str] = "\\"


def escape_like(value: str) -> str:
    """Makes text that is data behave like data inside a ``LIKE`` pattern.

    An identifier from 1C may contain a percent sign or an underscore, and both
    are wildcards to Postgres. Unescaped, a category whose path holds one would
    quietly list a different subtree.
    """
    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    return escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")


def stock_total() -> ColumnElement[object]:
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


def price_join(price_type_id: PriceTypeId) -> ColumnElement[bool]:
    """The price of a product under one price list, if there is one."""
    return and_(
        catalog_prices_table.c.product_id == catalog_products_table.c.id,
        catalog_prices_table.c.price_type_id == price_type_id.value,
    )


def listing_select(price_type_id: PriceTypeId) -> Select[tuple[object, ...]]:
    """The columns every list of products is built from, priced and stocked."""
    return select(
        catalog_products_table.c.id,
        catalog_products_table.c.sku,
        catalog_products_table.c.name,
        catalog_products_table.c.unit_name,
        catalog_prices_table.c.amount,
        catalog_prices_table.c.currency,
        stock_total(),
    ).select_from(
        catalog_products_table.outerjoin(catalog_prices_table, price_join(price_type_id)),
    )


def listing_order(sorting: ProductSorting) -> tuple[ColumnElement[object], ...]:
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


def in_subtree_of(path: str) -> ColumnElement[bool]:
    """Products of the group at ``path`` and of every group under it.

    The pattern is bound as a parameter rather than computed inside the
    statement, which is what lets the btree index on ``path`` be used at all,
    and what lets the ``%`` and ``_`` an identifier may contain be escaped
    before Postgres reads them as wildcards.
    """
    subtree = select(catalog_categories_table.c.id).where(
        or_(
            catalog_categories_table.c.path == path,
            catalog_categories_table.c.path.like(
                f"{escape_like(path)}{PATH_SEPARATOR}%",
                escape=LIKE_ESCAPE,
            ),
        ),
    )

    return catalog_products_table.c.category_id.in_(subtree)


def paginate(
    stmt: Select[tuple[object, ...]],
    pagination: Pagination,
) -> Select[tuple[object, ...]]:
    if pagination.limit is not None:
        stmt = stmt.limit(pagination.limit)
    if pagination.offset is not None:
        stmt = stmt.offset(pagination.offset)

    return stmt
