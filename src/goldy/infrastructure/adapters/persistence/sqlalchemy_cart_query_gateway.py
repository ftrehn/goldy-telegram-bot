import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Final, override
from uuid import UUID

from sqlalchemy import Label, RowMapping, and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.carts import CartQueryGateway
from goldy.application.common.views.cart import CartView
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.cart_row_view_mapper import CartRowViewMapper
from goldy.infrastructure.persistence.models import (
    cart_items_table,
    carts_table,
    catalog_prices_table,
    catalog_products_table,
    catalog_stock_table,
)

if TYPE_CHECKING:
    from goldy.domain.catalog.values.price_type_id import PriceTypeId
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyCartQueryGateway(CartQueryGateway):
    """Draws the cart screen: quantities from the cart, everything else joined.

    The cart stores no price of its own, so the price, the name, the unit and
    the stock figure are all read from the projection on every render. That is
    what makes assigning a new price type reprice a standing cart at once
    instead of leaving numbers in it that the shop no longer offers.

    The join against the products is a ``LEFT JOIN`` and carries **no
    ``is_active`` filter**. The filter looks natural and is wrong: with it a
    withdrawn product would drop out of the screen and the total would quietly
    shrink, and nobody notices what is not there. The line comes back marked
    instead, and the screen offers to clear it.

    Stock plays no part in that mark. It is an advisory projection of 1C with
    no reservation behind it — a product at zero is sold to order — so it is
    summed over the warehouses, printed as a badge, and never allowed to hide
    "checkout". The availability predicate here is "the catalog still holds an
    active product", which is the same one
    ``CatalogQueryGateway.read_existing_product_ids`` answers with; if the two
    disagreed, "remove unavailable" would either take a line the screen showed
    as fine or leave one it showed as broken.

    The rows become a view in ``CartRowViewMapper``, injected like every other
    row mapper: this class knows the query, the mapper knows the shape, and
    neither has to change for the other.
    """

    def __init__(
        self,
        session: AsyncSession,
        cart_row_view_mapper: CartRowViewMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._mapper: Final[CartRowViewMapper] = cart_row_view_mapper

    @override
    async def read_for(
        self,
        user_id: UserId,
        price_type_id: PriceTypeId,
    ) -> CartView | None:
        cart_id = await self._cart_id_of(user_id)

        if cart_id is None:
            return None

        return self._mapper.to_cart_view(await self._read_lines(cart_id, price_type_id))

    async def _cart_id_of(self, user_id: UserId) -> UUID | None:
        """Tells "no cart at all" from "a cart with nothing in it".

        Both are ordinary — one is somebody who has just registered, the other
        somebody who has just checked out — and the port promises ``None`` for
        the first, so the existence of the row has to be established before the
        lines are read.
        """
        stmt = select(carts_table.c.id).where(carts_table.c.user_id == user_id)

        try:
            return (await self._session.execute(stmt)).scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the cart id")
            msg = "Failed to read the cart id."
            raise RepoError(msg) from e

    async def _read_lines(
        self,
        cart_id: UUID,
        price_type_id: PriceTypeId,
    ) -> Sequence[RowMapping]:
        stmt = (
            select(
                cart_items_table.c.product_id,
                cart_items_table.c.quantity,
                catalog_products_table.c.sku,
                catalog_products_table.c.name,
                catalog_products_table.c.unit_name,
                catalog_products_table.c.is_active,
                catalog_prices_table.c.amount,
                catalog_prices_table.c.currency,
                self._stock_column(),
            )
            .select_from(cart_items_table)
            .outerjoin(
                catalog_products_table,
                catalog_products_table.c.id == cart_items_table.c.product_id,
            )
            .outerjoin(
                catalog_prices_table,
                and_(
                    catalog_prices_table.c.product_id == cart_items_table.c.product_id,
                    catalog_prices_table.c.price_type_id == price_type_id.value,
                ),
            )
            .where(cart_items_table.c.cart_id == cart_id)
            .order_by(cart_items_table.c.added_at)
        )

        try:
            return (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read the cart lines")
            msg = "Failed to read the cart lines."
            raise RepoError(msg) from e

    def _stock_column(self) -> Label[Decimal]:
        """Sums the warehouses, which is what makes warehouses a non-event.

        The 1C extension exports the one warehouse it is configured with,
        but the sum is written from the first day: more warehouses appearing
        then change neither this query nor the view it fills.

        Correlated per line rather than joined against one grouped subquery. A
        cart holds at most a hundred products, so this is a hundred index seeks
        on the primary key of the stock table; the grouped subquery reads as
        tidier and makes the database aggregate the stock of the entire catalog
        before throwing all but a hundred rows of it away, because a predicate
        cannot be pushed through an outer join into an aggregate.
        """
        return (
            select(func.sum(catalog_stock_table.c.quantity))
            .where(catalog_stock_table.c.product_id == cart_items_table.c.product_id)
            .correlate(cart_items_table)
            .scalar_subquery()
            .label("stock")
        )
