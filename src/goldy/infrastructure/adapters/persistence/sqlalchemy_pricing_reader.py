import logging
from collections.abc import Sequence
from typing import Final, final, override

from sqlalchemy import Executable, RowMapping, and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.catalog import (
    CartPrices,
    PricingReader,
    ResolvedPriceType,
)
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.users.values.user_id import UserId
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.pricing_row_mapper import PricingRowMapper
from goldy.infrastructure.persistence.models import (
    catalog_price_type_bindings_table,
    catalog_price_types_table,
    catalog_prices_table,
    catalog_products_table,
    users_table,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class SqlAlchemyPricingReader(PricingReader):
    """Reads the same prices the storefront shows, to keep them in an order.

    Nothing here is cached and nothing here may be: these rows become the
    snapshot on an order line, and a stale number there is a wrong total on a
    document somebody will be invoiced against.

    The configured default price list arrives already parsed, in the
    constructor, exactly as ``StaticAdminRegistry`` receives parsed phone
    numbers. Infrastructure must not import ``setup``, so the composition root
    builds the value and hands it over.

    The binding is keyed by phone number rather than by user id, so resolving a
    price list is a join from ``users`` into the projection and not a lookup of
    something the bot stores about a person. A customer whose number 1C has
    never mentioned falls back to the configured list in the same statement,
    which is why this costs one round trip and not two.
    """

    def __init__(
        self,
        session: AsyncSession,
        default_price_type_id: PriceTypeId,
        pricing_row_mapper: PricingRowMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._default_price_type_id: Final[PriceTypeId] = default_price_type_id
        self._mapper: Final[PricingRowMapper] = pricing_row_mapper

    @override
    async def read_price_type_for(self, user_id: UserId) -> ResolvedPriceType | None:
        bound = (
            select(catalog_price_type_bindings_table.c.price_type_id)
            .select_from(
                catalog_price_type_bindings_table.join(
                    users_table,
                    users_table.c.phone_number
                    == catalog_price_type_bindings_table.c.phone_number,
                ),
            )
            .where(users_table.c.id == user_id)
            .limit(1)
            .scalar_subquery()
        )
        resolved = func.coalesce(bound, self._default_price_type_id.value)

        stmt = select(
            catalog_price_types_table.c.id.label("price_type_id"),
            catalog_price_types_table.c.is_supported,
        ).where(catalog_price_types_table.c.id == resolved)

        row = await self._row(stmt, "the price type of the customer")
        return None if row is None else self._mapper.to_resolved_price_type(row)

    @override
    async def read_cart_prices(
        self,
        product_ids: Sequence[ProductId],
        price_type_id: PriceTypeId,
    ) -> CartPrices:
        """Every product of this list the catalog still holds, sorted by price.

        One outer join, and the rows fall on two sides of it. A row with an
        amount becomes a domain value; a row without one names a product the
        catalog lists but does not price under this list. The two are kept
        apart on purpose and answered by different errors upstream: collapsing
        them here would turn "we no longer sell this" into "ask a manager
        about the price".

        ``is_active`` is the same predicate the storefront's ``product_exists``
        uses. A withdrawn product must not be ordered under a price row that
        outlived it by a sweep.
        """
        if not product_ids:
            return CartPrices(priced_products=(), unpriced_product_ids=())

        stmt = (
            select(
                catalog_products_table.c.id.label("product_id"),
                catalog_products_table.c.sku,
                catalog_products_table.c.name,
                catalog_products_table.c.unit_id,
                catalog_products_table.c.unit_name,
                catalog_prices_table.c.amount,
                catalog_prices_table.c.currency,
            )
            .select_from(
                catalog_products_table.outerjoin(
                    catalog_prices_table,
                    and_(
                        catalog_prices_table.c.product_id == catalog_products_table.c.id,
                        catalog_prices_table.c.price_type_id == price_type_id.value,
                    ),
                ),
            )
            .where(
                catalog_products_table.c.id.in_(
                    [product_id.value for product_id in product_ids],
                ),
                catalog_products_table.c.is_active,
            )
        )

        rows = await self._rows(stmt, "the prices of the cart")

        return CartPrices(
            priced_products=[
                self._mapper.to_priced_product(row)
                for row in rows
                if row["amount"] is not None
            ],
            unpriced_product_ids=[
                ProductId(value=row["product_id"])
                for row in rows
                if row["amount"] is None
            ],
        )

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
