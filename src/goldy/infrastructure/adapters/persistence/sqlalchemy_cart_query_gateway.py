import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Final, override
from uuid import UUID

from sqlalchemy import Label, RowMapping, and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.carts import CartQueryGateway
from goldy.application.common.views.cart import CartLineView, CartView
from goldy.application.common.views.money import MoneyView
from goldy.infrastructure.errors import RepoError
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

    The views are built here rather than by a row mapper of their own. The
    user read model needs one because its accounts arrive from a second query
    and are grafted onto rows the same mapper also serves the admin list with;
    a cart is one query feeding one view, and a port for it would be an extra
    thing to wire for no second caller.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def read_for(
        self,
        user_id: UserId,
        price_type_id: PriceTypeId,
    ) -> CartView | None:
        cart_id = await self._cart_id_of(user_id)

        if cart_id is None:
            return None

        rows = await self._read_lines(cart_id, price_type_id)
        lines = tuple(self._to_line_view(row) for row in rows)

        return CartView(lines=lines, total=self._total_of(lines))

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

        1C gives no breakdown yet and the consumer writes a fixed warehouse,
        but the sum is written from the first day: real warehouses appearing
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

    def _to_line_view(self, row: RowMapping) -> CartLineView:
        """Flattens one joined row, unwrapping what the type decorators built.

        Only two columns need unwrapping, and which two is not obvious: the
        cart's own ``product_id`` and ``quantity`` carry type decorators and
        arrive as value objects, while everything joined in comes from the
        projection, which is Core-only and hands back plain text and numbers.

        ``amount`` being NULL is an ordinary state and not a defect: this
        customer's price type simply prices no such product. The line keeps its
        quantity and loses its price, the screen prints "price on request", and
        the total below counts what it can — printing a zero would read as
        "free".
        """
        quantity: int = row["quantity"].value
        amount: Decimal | None = row["amount"]
        currency: str | None = row["currency"]

        unit_price = (
            MoneyView(amount=amount, currency=currency)
            if amount is not None and currency is not None
            else None
        )
        line_total = (
            MoneyView(amount=amount * quantity, currency=currency)
            if amount is not None and currency is not None
            else None
        )

        return CartLineView(
            product_id=row["product_id"].value,
            sku=row["sku"],
            name=row["name"],
            unit_name=row["unit_name"],
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            stock=row["stock"],
            is_available=bool(row["is_active"]),
        )

    def _total_of(self, lines: Sequence[CartLineView]) -> MoneyView:
        """Adds up the lines that have a price, in the currency they share.

        Every price in the cart comes from one price type, and a price type is
        denominated in exactly one currency, so taking the currency off the
        first priced line cannot mix two. An unpriced line contributes nothing
        and is counted by ``CartView.has_unpriced_lines`` instead, which is
        what keeps "checkout" from being offered on a total that is short.
        """
        totals = [line.line_total for line in lines if line.line_total is not None]

        if not totals:
            return MoneyView.zero()

        return MoneyView(
            amount=sum((total.amount for total in totals), start=Decimal("0.00")),
            currency=totals[0].currency,
        )
