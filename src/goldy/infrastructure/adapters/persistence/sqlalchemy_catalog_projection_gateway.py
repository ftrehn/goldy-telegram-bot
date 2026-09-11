import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, override

from sqlalchemy import (
    ColumnElement,
    Table,
    UpdateBase,
    delete,
    func,
    literal_column,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.catalog import (
    CatalogProjectionGateway,
    CatalogScope,
    CatalogScopeKind,
    CategoryRow,
    PriceRow,
    PriceTypeBindingRow,
    PriceTypeRow,
    ProductRow,
    StockRow,
)
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.common.values.currency import Currency
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import (
    catalog_categories_table,
    catalog_price_type_bindings_table,
    catalog_price_types_table,
    catalog_prices_table,
    catalog_products_table,
    catalog_stock_table,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

PATH_SEPARATOR: Final[str] = "/"
"""What a category path joins the identifiers of its ancestors with.

The same separator ``SqlAlchemyCatalogQueryGateway`` selects a subtree by. A
path is written without a trailing separator, and a subtree is matched as "the
path itself, or the path followed by a separator", so a group whose identifier
merely starts with another's is not swallowed by it.
"""

SUPPORTED_CURRENCIES: Final[frozenset[str]] = frozenset(
    currency.value for currency in Currency
)


class SqlAlchemyCatalogProjectionGateway(CatalogProjectionGateway):
    """The only writer of the catalog projection.

    Every upsert is conditional on ``source_changed_at`` rather than merely
    keyed by identifier, and that condition is what makes a repeated delivery
    harmless. RabbitMQ reorders messages and repeats them after a restart,
    while ``synced_at`` is stamped by us and therefore cannot tell a fresh
    message from an old one replayed: without the condition a replayed old
    price would overwrite a new one and mark itself fresh, after which the
    sweep would leave it alone forever.

    A row that carries no ``source_changed_at``, on either side, is taken as
    the newer one. The column is filled by the exchange, today by a fixture,
    and refusing rows for lacking it would mean refusing the whole catalog
    until 1C starts sending it.

    Two things are decided here rather than by a handler, because both are
    properties of the projection rather than of a use case. A category's
    ``path`` and ``depth`` are computed from the batch as a whole, which the
    contract guarantees is the complete category snapshot; a price type's
    ``is_supported`` is whether the currency 1C spelled is one this service
    knows, and an unsupported list is stored rather than dropped so a customer
    bound to it is refused plainly instead of shown roubles that are not theirs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def upsert_categories(
        self,
        categories: Sequence[CategoryRow],
        batch_id: str,
    ) -> int:
        synced_at = datetime.now(UTC)
        placements = _placements(categories)
        values = [
            {
                "id": row.id,
                "parent_id": row.parent_id,
                "name": row.name,
                "path": placements[row.id].path,
                "depth": placements[row.id].depth,
                "is_active": True,
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in categories
        ]

        return await self._upsert(catalog_categories_table, values, "categories")

    @override
    async def upsert_products(self, products: Sequence[ProductRow], batch_id: str) -> int:
        synced_at = datetime.now(UTC)
        values = [
            {
                "id": row.id,
                "sku": row.sku,
                "name": row.name,
                "full_name": row.full_name,
                "category_id": row.category_id,
                "unit_id": row.unit_id,
                "unit_name": row.unit_name,
                "unit_ratio": row.unit_ratio,
                "description": row.description,
                "image_url": row.image_url,
                "is_active": True,
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in products
        ]

        return await self._upsert(catalog_products_table, values, "products")

    @override
    async def upsert_price_types(
        self,
        price_types: Sequence[PriceTypeRow],
        batch_id: str,
    ) -> int:
        synced_at = datetime.now(UTC)
        values = [
            {
                "id": row.id,
                "name": row.name,
                "currency": row.currency.strip(),
                "is_supported": _is_supported(row.currency),
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in price_types
        ]

        return await self._upsert(catalog_price_types_table, values, "price types")

    @override
    async def upsert_prices(self, prices: Sequence[PriceRow], batch_id: str) -> int:
        synced_at = datetime.now(UTC)
        values = [
            {
                "product_id": row.product_id,
                "price_type_id": row.price_type_id,
                "amount": row.amount,
                "currency": row.currency.strip(),
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in prices
        ]

        return await self._upsert(catalog_prices_table, values, "prices")

    @override
    async def upsert_stock(self, stock: Sequence[StockRow], batch_id: str) -> int:
        synced_at = datetime.now(UTC)
        values = [
            {
                "product_id": row.product_id,
                "warehouse_id": row.warehouse_id,
                "quantity": row.quantity,
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in stock
        ]

        return await self._upsert(catalog_stock_table, values, "stock")

    @override
    async def upsert_price_type_bindings(
        self,
        bindings: Sequence[PriceTypeBindingRow],
        batch_id: str,
    ) -> int:
        synced_at = datetime.now(UTC)
        values = [
            {
                "phone_number": row.phone_number,
                "price_type_id": row.price_type_id,
                "source_counterparty_id": row.source_counterparty_id,
                "batch_id": batch_id,
                "source_changed_at": row.source_changed_at,
                "synced_at": synced_at,
            }
            for row in bindings
        ]

        return await self._upsert(
            catalog_price_type_bindings_table,
            values,
            "price type bindings",
        )

    @override
    async def finalize(self, scope: CatalogScope, batch_id: str) -> int:
        """Removes what this batch did not mention, as its scope defines it.

        Three different sweeps, and confusing them is expensive. Products and
        categories are deactivated and live forever, because placed orders
        point at them and a card is expected to open in a customer's history.
        Everything else is deleted: a price withdrawn in 1C that survives in
        the projection is a price the shop does not offer, a binding that
        survives keeps a customer on a list nobody assigned them, and a price
        type that survives keeps both alive.

        The qualifier on prices and stock is what keeps a single price list
        from wiping every other one, and it is applied only when the scope
        carries it — a full export of every price list carries none.
        """
        match scope.kind:
            case CatalogScopeKind.CATEGORIES:
                return await self._deactivate(catalog_categories_table, batch_id)
            case CatalogScopeKind.PRODUCTS:
                return await self._deactivate(catalog_products_table, batch_id)
            case CatalogScopeKind.PRICE_TYPES:
                return await self._sweep(catalog_price_types_table, batch_id, ())
            case CatalogScopeKind.PRICES:
                return await self._sweep(
                    catalog_prices_table,
                    batch_id,
                    _qualifier(
                        catalog_prices_table, "price_type_id", scope.price_type_id
                    ),
                )
            case CatalogScopeKind.STOCK:
                return await self._sweep(
                    catalog_stock_table,
                    batch_id,
                    _qualifier(catalog_stock_table, "warehouse_id", scope.warehouse_id),
                )
            case CatalogScopeKind.BINDINGS:
                return await self._sweep(
                    catalog_price_type_bindings_table,
                    batch_id,
                    (),
                )

    @override
    async def has_price_type(self, price_type_id: PriceTypeId) -> bool:
        stmt = (
            select(catalog_price_types_table.c.id)
            .where(catalog_price_types_table.c.id == price_type_id.value)
            .limit(1)
        )

        try:
            row = (await self._session.execute(stmt)).one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the price type")
            msg = "Failed to read the price type."
            raise RepoError(msg) from e

        return row is not None

    async def _upsert(
        self,
        table: Table,
        values: Sequence[Mapping[str, object]],
        what: str,
    ) -> int:
        """Writes one batch of rows, never downgrading a row to an older one.

        Generated columns are left out of the update on purpose: Postgres
        computes them and refuses to be told what they are.
        """
        if not values:
            return 0

        stmt = postgresql_insert(table).values(list(values))
        keys = [column.name for column in table.primary_key.columns]
        updates = {
            column.name: stmt.excluded[column.name]
            for column in table.columns
            if column.name not in keys and column.computed is None
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=keys,
            set_=updates,
            where=or_(
                stmt.excluded["source_changed_at"].is_(None),
                table.c.source_changed_at.is_(None),
                stmt.excluded["source_changed_at"] >= table.c.source_changed_at,
            ),
        )

        return await self._count_written(stmt, f"upsert {what}")

    async def _deactivate(self, table: Table, batch_id: str) -> int:
        """Hides what the batch did not mention, keeping the row itself.

        ``synced_at`` is deliberately left alone. It records when the source
        last delivered this row, and a sweep is us noticing an absence rather
        than the source saying anything about it.
        """
        stmt = (
            update(table)
            .where(table.c.batch_id != batch_id, table.c.is_active)
            .values(is_active=False)
        )

        return await self._count_written(stmt, f"deactivate rows of '{table.name}'")

    async def _sweep(
        self,
        table: Table,
        batch_id: str,
        qualifier: Sequence[ColumnElement[bool]],
    ) -> int:
        stmt = delete(table).where(table.c.batch_id != batch_id, *qualifier)

        return await self._count_written(stmt, f"sweep rows of '{table.name}'")

    async def _count_written(self, statement: UpdateBase, what: str) -> int:
        """Runs a write and brings back how many rows it actually touched.

        Counted server-side through a data-modifying CTE rather than by
        fetching the rows back, because a sweep of a large price list is tens
        of thousands of rows and nobody wants them — only how many there were.

        Counting is not decoration either. An upsert that refuses to downgrade
        a row writes fewer rows than it was given, and the difference between
        "took your batch" and "ignored half of it as stale" is the line an
        import log exists to show.
        """
        counted = select(func.count()).select_from(
            statement.returning(literal_column("1")).cte("written"),
        )

        try:
            return (await self._session.execute(counted)).scalar_one()
        except SQLAlchemyError as e:
            logger.exception("failed to %s", what)
            msg = f"Failed to {what}."
            raise RepoError(msg) from e


@dataclass(frozen=True, slots=True)
class _Placement:
    """Where one category sits in the tree the batch describes."""

    path: str
    depth: int


def _placements(categories: Sequence[CategoryRow]) -> dict[str, _Placement]:
    """Walks every category up to its root, once per batch.

    Computed here rather than sent by the exchange because it is derived from
    the batch as a whole, and that is only possible because the contract
    requires the category snapshot to be complete and to arrive in one message.
    A recursive query over the table would do the same without the column, but
    it would need every parent to have landed already, and RabbitMQ promises no
    such order.

    A parent that is not in the batch ends the walk, and so does a cycle. Both
    are broken snapshots, and neither is worth failing a whole import over: the
    category simply sits higher in the tree than it should, which is visible on
    the storefront and fixable by the next export.
    """
    parents = {row.id: row.parent_id for row in categories}
    placements: dict[str, _Placement] = {}

    for row in categories:
        ancestry = [row.id]
        seen = {row.id}
        parent_id = row.parent_id

        while parent_id is not None and parent_id in parents and parent_id not in seen:
            ancestry.append(parent_id)
            seen.add(parent_id)
            parent_id = parents[parent_id]

        ancestry.reverse()
        placements[row.id] = _Placement(
            path=PATH_SEPARATOR.join(ancestry),
            depth=len(ancestry) - 1,
        )

    return placements


def _qualifier(
    table: Table,
    column_name: str,
    value: str | None,
) -> tuple[ColumnElement[bool], ...]:
    """Narrows a sweep to the one price list or warehouse the batch was about."""
    return () if value is None else (table.c[column_name] == value,)


def _is_supported(currency: str) -> bool:
    """Whether this shop can price in what 1C denominated the list in.

    1C spells currency codes in upper case and our enum in lower, so the
    comparison is made on one of them rather than on whichever arrived.
    """
    return currency.strip().lower() in SUPPORTED_CURRENCIES
