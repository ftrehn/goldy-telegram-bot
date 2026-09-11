import logging
from collections.abc import Sequence
from typing import Final, override

from sqlalchemy import Executable, RowMapping, and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.catalog import PricingGateway
from goldy.application.common.views.catalog import PriceTypeView, PricedProductView
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.users.values.user_id import UserId
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.catalog_row_view_mapper import CatalogRowViewMapper
from goldy.infrastructure.persistence.models import (
    catalog_price_type_bindings_table,
    catalog_price_types_table,
    catalog_prices_table,
    catalog_products_table,
    users_table,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyPricingGateway(PricingGateway):
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
        catalog_row_view_mapper: CatalogRowViewMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._default_price_type_id: Final[PriceTypeId] = default_price_type_id
        self._mapper: Final[CatalogRowViewMapper] = catalog_row_view_mapper

    @override
    async def read_price_type_for(self, user_id: UserId) -> PriceTypeView | None:
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
        return None if row is None else self._mapper.to_price_type_view(row)

    @override
    async def read_priced_products(
        self,
        product_ids: Sequence[ProductId],
        price_type_id: PriceTypeId,
    ) -> Sequence[PricedProductView]:
        """Every product of this list the catalog still holds, priced or not.

        The two absences are kept apart on purpose and answered by different
        errors upstream: a product missing from the result is gone from the
        catalog, while a product present without a price has no row under this
        price list. Collapsing them here would turn "we no longer sell this"
        into "ask a manager about the price".

        ``is_active`` is the same predicate the storefront's ``product_exists``
        uses. A withdrawn product must not be ordered under a price row that
        outlived it by a sweep.
        """
        if not product_ids:
            return ()

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
        return [self._mapper.to_priced_product_view(row) for row in rows]

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
