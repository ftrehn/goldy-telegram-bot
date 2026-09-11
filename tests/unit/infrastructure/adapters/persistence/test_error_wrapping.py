"""No SQLAlchemy exception leaves a persistence adapter, from any entry point.

This is the promise the whole error story rests on. Handlers are forbidden to
catch ``Exception`` and catch ``AppError`` instead, and the Telegram error
handler renders by walking the MRO of a domain error — so a ``SQLAlchemyError``
escaping one gateway is not a bad message, it is no message at all.

The interesting part is that the promise has to hold at every public method
rather than for each class once. A gateway with six reads and a ``try`` around
five of them type-checks, reads fine and fails in production on the sixth, so
the methods are listed here one by one.

``SqlAlchemyCartCommandGateway`` is missing from the list, and not by oversight.
Both of its methods build ``select(Cart)``, which needs the imperative mapping,
and mapping the classes here would make ``setup_map_tables()`` run twice in a
process the moment the integration suite runs alongside this one. Its wrapping
is covered where the mapping exists.
"""

from collections.abc import Awaitable, Callable
from typing import Final

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.query_params.catalog_filters import (
    ProductFilters,
    ProductSorting,
)
from goldy.application.common.query_params.order_filters import (
    OrderFilters,
    OrderSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.search_term import SearchTerm
from goldy.domain.catalog.values.category_id import CategoryId
from goldy.infrastructure.adapters.persistence import (
    sqlalchemy_catalog_projection_gateway as projection,
)
from goldy.infrastructure.adapters.persistence.postgres_order_number_generator import (
    PostgresOrderNumberGenerator,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_cart_query_gateway import (
    SqlAlchemyCartQueryGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_catalog_query_gateway import (
    SqlAlchemyCatalogQueryGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_order_command_gateway import (
    SqlAlchemyOrderCommandGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_order_query_gateway import (
    SqlAlchemyOrderQueryGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_pricing_gateway import (
    SqlAlchemyPricingGateway,
)
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.sqlalchemy_catalog_row_view_mapper import (
    SqlAlchemyCatalogRowViewMapper,
)
from goldy.infrastructure.mappers.sqlalchemy_order_row_view_mapper import (
    SqlAlchemyOrderRowViewMapper,
)
from tests.unit.factories.catalog_factories import make_scope
from tests.unit.factories.domain_factories import make_events_collection, make_user_id
from tests.unit.factories.shop_factories import (
    make_order,
    make_order_id,
    make_price_type_id,
    make_product_id,
)
from tests.unit.stubs.persistence import failing_session

type Call = Callable[[AsyncSession], Awaitable[object]]


def _catalog_queries(session: AsyncSession) -> SqlAlchemyCatalogQueryGateway:
    return SqlAlchemyCatalogQueryGateway(session, SqlAlchemyCatalogRowViewMapper())


def _pricing(session: AsyncSession) -> SqlAlchemyPricingGateway:
    return SqlAlchemyPricingGateway(
        session,
        make_price_type_id(),
        SqlAlchemyCatalogRowViewMapper(),
    )


def _orders(session: AsyncSession) -> SqlAlchemyOrderCommandGateway:
    return SqlAlchemyOrderCommandGateway(session, make_events_collection())


def _projection(session: AsyncSession) -> projection.SqlAlchemyCatalogProjectionGateway:
    return projection.SqlAlchemyCatalogProjectionGateway(session)


def _order_queries(session: AsyncSession) -> SqlAlchemyOrderQueryGateway:
    return SqlAlchemyOrderQueryGateway(session, SqlAlchemyOrderRowViewMapper())


async def _add_an_order(session: AsyncSession) -> object:
    order, _ = make_order()
    await _orders(session).add(order)
    return None


CALLS: Final[dict[str, Call]] = {
    "order number generator": lambda session: PostgresOrderNumberGenerator(session)(),
    "catalog: categories": lambda session: _catalog_queries(session).read_categories(
        None,
    ),
    "catalog: one category": lambda session: _catalog_queries(session).read_category(
        CategoryId(value="1c-category-1"),
    ),
    "catalog: product card": lambda session: _catalog_queries(session).read_product(
        make_product_id(),
        make_price_type_id(),
    ),
    "catalog: product exists": lambda session: _catalog_queries(session).product_exists(
        make_product_id(),
    ),
    "catalog: existing ids": lambda session: _catalog_queries(
        session,
    ).read_existing_product_ids((make_product_id(),)),
    "catalog: listing": lambda session: _catalog_queries(session).read_products(
        filters=ProductFilters(),
        price_type_id=make_price_type_id(),
        pagination=Pagination(),
        sorting=ProductSorting(),
    ),
    "catalog: search": lambda session: _catalog_queries(session).search_products(
        term=SearchTerm(value="дрель"),
        price_type_id=make_price_type_id(),
        pagination=Pagination(),
    ),
    "projection: has price type": lambda session: _projection(session).has_price_type(
        make_price_type_id(),
    ),
    "projection: finalize": lambda session: _projection(session).finalize(
        make_scope(),
        "batch-0001",
    ),
    "pricing: price type of a customer": lambda session: _pricing(
        session,
    ).read_price_type_for(make_user_id()),
    "pricing: priced products": lambda session: _pricing(session).read_priced_products(
        (make_product_id(),),
        make_price_type_id(),
    ),
    "cart: the cart screen": lambda session: SqlAlchemyCartQueryGateway(session).read_for(
        make_user_id(),
        make_price_type_id(),
    ),
    "order: add": _add_an_order,
    "order: by id": lambda session: _orders(session).by_id(make_order_id()),
    "order: the card": lambda session: _order_queries(session).read_by_id(
        make_order_id(),
    ),
    "order: a customer's history": lambda session: _order_queries(
        session,
    ).read_for_customer(
        customer_id=make_user_id(),
        filters=OrderFilters(),
        pagination=Pagination(),
        sorting=OrderSorting(),
    ),
    "order: the staff queue": lambda session: _order_queries(session).read_all(
        filters=OrderFilters(),
        pagination=Pagination(),
        sorting=OrderSorting(),
    ),
    "order: last delivery address": lambda session: _order_queries(
        session,
    ).read_last_delivery_address(make_user_id()),
}


@pytest.mark.parametrize("call", CALLS.values(), ids=list(CALLS))
async def test_a_library_failure_leaves_the_adapter_as_our_own_error(
    call: Call,
) -> None:
    """Wrapped, and with the original kept as the cause so a log still names it."""
    with pytest.raises(RepoError) as failure:
        await call(failing_session())

    assert isinstance(failure.value.__cause__, SQLAlchemyError)
