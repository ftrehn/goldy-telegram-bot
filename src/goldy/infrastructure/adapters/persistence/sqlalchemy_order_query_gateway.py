import logging
from typing import Final, override

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    Numeric,
    RowMapping,
    Select,
    String,
    Subquery,
    cast,
    func,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.query_params.order_filters import (
    OrderFilters,
    OrderSortField,
    OrderSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.order import (
    OrderLineView,
    OrderListView,
    OrderView,
)
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.values.user_id import UserId
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.order_row_view_mapper import OrderRowViewMapper
from goldy.infrastructure.persistence.models import (
    catalog_stock_table,
    order_items_table,
    orders_table,
    users_table,
)
from goldy.infrastructure.persistence.models.types import (
    MAX_CURRENCY_COLUMN_LENGTH,
    MEASURE_COLUMN_PRECISION,
    MEASURE_COLUMN_SCALE,
    MONEY_COLUMN_PRECISION,
    MONEY_COLUMN_SCALE,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

line_totals: Final[Subquery] = (
    select(
        order_items_table.c.order_id.label("order_id"),
        func.sum(
            order_items_table.c.unit_price_amount * order_items_table.c.quantity,
            type_=Numeric(MONEY_COLUMN_PRECISION, MONEY_COLUMN_SCALE),
        ).label("total_amount"),
        func.min(
            order_items_table.c.unit_price_currency,
            type_=String(MAX_CURRENCY_COLUMN_LENGTH),
        ).label("total_currency"),
        func.count().label("line_count"),
    )
    .group_by(order_items_table.c.order_id)
    .subquery("line_totals")
)
"""What a listed order comes to, summed where the rows already are.

``Order.total`` gets the same number out of the same lines, but a list exists
to be printed: loading fifty aggregates with their lines to print fifty numbers
is how the staff queue gets slow.

The currency is taken with ``min`` rather than joined for, because an order is
priced in exactly one currency and ``Order.place`` refuses anything else, so
any line's currency is the order's. Both aggregates carry an explicit type so
the result arrives as a plain amount and a plain string: the columns under them
carry decorators, and a value object rebuilt here would only have to be
unwrapped again by the mapper.
"""

product_stock: Final[Subquery] = (
    select(
        catalog_stock_table.c.product_id.label("product_id"),
        func.sum(
            catalog_stock_table.c.quantity,
            type_=Numeric(MEASURE_COLUMN_PRECISION, MEASURE_COLUMN_SCALE),
        ).label("quantity"),
    )
    .group_by(catalog_stock_table.c.product_id)
    .subquery("product_stock")
)
"""Today's free stock per product, summed across warehouses.

Grouped from the first day although 1C gives no warehouse breakdown yet and
every row carries a fixed warehouse: real warehouses appearing later then
changes neither this statement nor anything that reads it.
"""


class SqlAlchemyOrderQueryGateway(OrderQueryGateway):
    """DAO for order cards, a customer's history and the staff queue.

    Selects the tables directly and hands back views: a page of orders is going
    to be rendered rather than reasoned about, and hydrating aggregates to
    print a table buys nothing. Totals are summed in SQL for the same reason.

    A card costs two round trips - the order, then its lines - rather than one
    join that would repeat the order row once per line and have to be collapsed
    in Python again.

    The lines are joined to the current stock, which is the one figure on a
    card that is not part of the order: a manager about to confirm needs to see
    what is on the shelf beside what was ordered. The join is always made,
    because this gateway cannot know who is asking and must not - who may open
    a card is decided by ``GetOrderQuery`` after the row has been read, and a
    customer's screen simply does not draw the column.
    """

    def __init__(
        self,
        session: AsyncSession,
        order_row_view_mapper: OrderRowViewMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._mapper: Final[OrderRowViewMapper] = order_row_view_mapper

    @override
    async def read_by_id(self, order_id: OrderId) -> OrderView | None:
        """One order card, for whoever turns out to be allowed to see it.

        Raises:
            RepoError: the order could not be read.
        """
        stmt = (
            select(orders_table, users_table.c.status.label("customer_status"))
            .select_from(orders_table)
            .join(users_table, users_table.c.id == orders_table.c.customer_id)
            .where(orders_table.c.id == order_id)
        )

        row = await self._one_or_none(stmt)

        if row is None:
            return None

        return self._mapper.to_view(row, await self._lines_of(order_id))

    @override
    async def read_for_customer(
        self,
        *,
        customer_id: UserId,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        """One page of this person's own orders, newest first by default.

        Raises:
            RepoError: the page could not be read.
        """
        return await self._page(
            conditions=[
                orders_table.c.customer_id == customer_id,
                *_conditions(filters),
            ],
            pagination=pagination,
            sorting=sorting,
        )

    @override
    async def read_all(
        self,
        *,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        """One page of the staff queue, across every customer.

        Raises:
            RepoError: the page could not be read.
        """
        return await self._page(
            conditions=_conditions(filters),
            pagination=pagination,
            sorting=sorting,
        )

    @override
    async def read_last_delivery_address(self, customer_id: UserId) -> str | None:
        """Where this person's most recent order went, or nothing.

        Raises:
            RepoError: the address could not be read.
        """
        stmt = (
            select(orders_table.c.delivery_address)
            .where(orders_table.c.customer_id == customer_id)
            .order_by(orders_table.c.created_at.desc())
            .limit(1)
        )

        try:
            address = (await self._session.execute(stmt)).scalars().one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the last delivery address")
            msg = "Failed to read the last delivery address."
            raise RepoError(msg) from e

        return address.value if address is not None else None

    async def _page(
        self,
        *,
        conditions: list[ColumnElement[bool]],
        pagination: Pagination,
        sorting: OrderSorting,
    ) -> OrderListView:
        """The rows of one page together with the count the pager needs.

        Two statements rather than a window function: the count is asked of
        the same filters without the page, and a pager that knows only its own
        slice cannot say how many pages there are.

        Ordering by number casts it to an integer first. The column holds text
        because the number is a label somebody reads out rather than an amount,
        and text ordering files order 10000 ahead of order 9999 the day the
        sequence reaches five digits.

        Raises:
            RepoError: the page could not be read.
        """
        sort_column = (
            cast(orders_table.c.number, BigInteger)
            if sorting.sort_by is OrderSortField.NUMBER
            else orders_table.c.created_at
        )
        descending = sorting.order is SortingOrder.DESC

        stmt = (
            select(
                orders_table.c.id,
                orders_table.c.number,
                orders_table.c.customer_id,
                orders_table.c.status,
                orders_table.c.created_at,
                users_table.c.first_name.label("customer_first_name"),
                users_table.c.last_name.label("customer_last_name"),
                users_table.c.status.label("customer_status"),
                line_totals.c.total_amount,
                line_totals.c.total_currency,
                func.coalesce(line_totals.c.line_count, 0).label("line_count"),
            )
            .select_from(orders_table)
            .join(users_table, users_table.c.id == orders_table.c.customer_id)
            .outerjoin(line_totals, line_totals.c.order_id == orders_table.c.id)
            .where(*conditions)
            .order_by(sort_column.desc() if descending else sort_column.asc())
        )

        if pagination.limit is not None:
            stmt = stmt.limit(pagination.limit)
        if pagination.offset is not None:
            stmt = stmt.offset(pagination.offset)

        try:
            rows = (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read the order list")
            msg = "Failed to read the order list."
            raise RepoError(msg) from e

        return OrderListView(
            orders=tuple(self._mapper.to_list_item_view(row) for row in rows),
            total=await self._total(conditions),
        )

    async def _total(self, conditions: list[ColumnElement[bool]]) -> int:
        """How many orders the same filters match, the page aside.

        Raises:
            RepoError: the orders could not be counted.
        """
        stmt = select(func.count()).select_from(orders_table).where(*conditions)

        try:
            return (await self._session.execute(stmt)).scalar_one()
        except SQLAlchemyError as e:
            logger.exception("failed to count orders")
            msg = "Failed to count orders."
            raise RepoError(msg) from e

    async def _lines_of(self, order_id: OrderId) -> list[OrderLineView]:
        """The snapshot lines of one order, with the stock there is today.

        Raises:
            RepoError: the lines could not be read.
        """
        stmt = (
            select(order_items_table, product_stock.c.quantity.label("stock"))
            .select_from(order_items_table)
            .outerjoin(
                product_stock,
                product_stock.c.product_id == order_items_table.c.product_id,
            )
            .where(order_items_table.c.order_id == order_id)
            .order_by(order_items_table.c.position)
        )

        try:
            rows = (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read the order lines")
            msg = "Failed to read the order lines."
            raise RepoError(msg) from e

        return [self._mapper.to_line_view(row) for row in rows]

    async def _one_or_none(self, stmt: Select[tuple[object, ...]]) -> RowMapping | None:
        """Runs a single-row statement, or says the order is not there.

        Raises:
            RepoError: the order view could not be read.
        """
        try:
            return (await self._session.execute(stmt)).mappings().one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the order view")
            msg = "Failed to read the order view."
            raise RepoError(msg) from e


def _conditions(filters: OrderFilters) -> list[ColumnElement[bool]]:
    """Narrows a list to what the filters name; unset means every order.

    Finished orders are not dropped by default, and the default is the point:
    where is the order I placed last spring is an ordinary question, and a
    history that hides what it considers over cannot answer it.
    """
    if filters.status is None:
        return []

    return [orders_table.c.status == filters.status]
