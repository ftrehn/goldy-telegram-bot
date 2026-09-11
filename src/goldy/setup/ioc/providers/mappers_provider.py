from typing import Final

from dishka import Provider, Scope

from goldy.application.common.ports.mappers import CartSummaryViewMapper, UserViewMapper
from goldy.infrastructure.mappers.adaptix_cart_summary_view_mapper import (
    AdaptixCartSummaryViewMapper,
)
from goldy.infrastructure.mappers.adaptix_user_view_mapper import AdaptixUserViewMapper
from goldy.infrastructure.mappers.catalog_row_view_mapper import CatalogRowViewMapper
from goldy.infrastructure.mappers.order_row_view_mapper import OrderRowViewMapper
from goldy.infrastructure.mappers.sqlalchemy_catalog_row_view_mapper import (
    SqlAlchemyCatalogRowViewMapper,
)
from goldy.infrastructure.mappers.sqlalchemy_order_row_view_mapper import (
    SqlAlchemyOrderRowViewMapper,
)
from goldy.infrastructure.mappers.sqlalchemy_user_row_view_mapper import (
    SqlAlchemyUserRowViewMapper,
)
from goldy.infrastructure.mappers.user_row_view_mapper import UserRowViewMapper


def mappers_provider() -> Provider:
    """Binds every mapping port to the adapter that performs it.

    ``APP`` scope, unlike the gateways: a mapper holds no session and no events
    collection, and the adaptix converters it calls are compiled once at import
    time. Rebuilding one per update would allocate for nothing.

    Two kinds of port meet here and the split is about their input. An
    aggregate mapper takes a domain object, so its port belongs among the
    application ports. A row mapper takes a ``sqlalchemy.RowMapping``, so its
    port stays in ``infrastructure.mappers`` — declaring it beside the others
    would put the ORM into the layer that must not know one.

    Every row mapper here is a dependency of a query gateway rather than of a
    handler. Leave one out and nothing complains about the mapper: the gateway
    that needed it simply stops resolving, and every container in the project
    refuses to build at startup.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.provide(source=AdaptixUserViewMapper, provides=UserViewMapper)
    provider.provide(
        source=AdaptixCartSummaryViewMapper,
        provides=CartSummaryViewMapper,
    )
    provider.provide(source=SqlAlchemyUserRowViewMapper, provides=UserRowViewMapper)
    provider.provide(
        source=SqlAlchemyCatalogRowViewMapper,
        provides=CatalogRowViewMapper,
    )
    provider.provide(source=SqlAlchemyOrderRowViewMapper, provides=OrderRowViewMapper)
    return provider
