from typing import Final

from dishka import Provider, Scope

from goldy.application.common.ports.admin_registry import AdminRegistry
from goldy.application.common.ports.carts import (
    CartCommandGateway,
    CartQueryGateway,
)
from goldy.application.common.ports.catalog import (
    CatalogProjectionGateway,
    CatalogQueryGateway,
    PricingGateway,
)
from goldy.application.common.ports.orders import (
    OrderCommandGateway,
    OrderQueryGateway,
)
from goldy.application.common.ports.outbox import (
    EventBus,
    EventSerializer,
    OutboxCommandGateway,
)
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.application.common.ports.users import (
    UserCommandGateway,
    UserQueryGateway,
)
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.infrastructure.adapters.auth.static_admin_registry import StaticAdminRegistry
from goldy.infrastructure.adapters.outbox.outbox_event_bus import OutboxEventBus
from goldy.infrastructure.adapters.outbox.retort_event_serializer import (
    RetortEventSerializer,
)
from goldy.infrastructure.adapters.persistence import (
    sqlalchemy_catalog_projection_gateway as projection_adapter,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_cart_command_gateway import (
    SqlAlchemyCartCommandGateway,
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
from goldy.infrastructure.adapters.persistence.sqlalchemy_outbox_command_gateway import (
    SqlAlchemyOutboxRepository,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_pricing_gateway import (
    SqlAlchemyPricingGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_transaction_manager import (
    SqlAlchemyTransactionManager,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_user_command_gateway import (
    SqlAlchemyUserCommandGateway,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_user_query_gateway import (
    SqlAlchemyUserQueryGateway,
)
from goldy.setup.configs.admin_config import AdminConfig
from goldy.setup.configs.catalog_config import CatalogConfig


def make_admin_registry(admin_config: AdminConfig) -> AdminRegistry:
    """Parses the configured numbers once, at startup.

    Built here rather than injected as a config, so the adapter never has to
    import ``setup`` — infrastructure depending on the composition root is how
    a project ends up unable to test either.
    """
    return StaticAdminRegistry.from_raw(admin_config.phone_numbers)


def make_default_price_type_id(catalog_config: CatalogConfig) -> PriceTypeId:
    """Parses the configured price list once, at startup.

    Two collaborators need this one value and neither may read the setting
    itself: ``SqlAlchemyPricingGateway`` substitutes it for a customer the
    catalog holds no binding for, and ``FinalizeCatalogImportHandler`` refuses
    a sweep that would leave the shop without it. Infrastructure must not
    import ``setup``, and the application layer must not either, so the
    identifier is built here and injected as a domain value - the same move
    that hands ``StaticAdminRegistry`` parsed numbers instead of a config.
    """
    return PriceTypeId(value=catalog_config.default_price_type_id.strip())


def gateways_provider() -> Provider:
    """Binds every application port to the adapter that implements it.

    ``REQUEST`` scope for everything built around the session or the events
    collection. The two ``APP``-scoped entries are the exception: both are
    configuration parsed once, and neither can change while the process runs.

    The shop ports - catalog, pricing, projection, carts and orders - are bound
    here too, to the SQLAlchemy adapters written against the same session every
    other gateway in a request shares. That is what makes a checkout atomic:
    the cart is emptied, the order is written and its events reach the outbox
    inside one transaction, because one session carries all three.

    Binding them here rather than in a storefront group of their own is
    deliberate. None of these adapters can answer "who is buying" - the
    handlers above them do that - so there is nothing about them a worker must
    be prevented from resolving, and a second place to look would only make a
    failed resolution harder to trace.

    The projection adapter is the one reached through its module rather than by
    name: its fully qualified import runs past the line limit, and a module
    alias is preferable to a ``noqa`` that would then be copied.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)

    provider.provide(source=SqlAlchemyTransactionManager, provides=TransactionManager)
    provider.provide(source=SqlAlchemyUserCommandGateway, provides=UserCommandGateway)
    provider.provide(source=SqlAlchemyUserQueryGateway, provides=UserQueryGateway)

    provider.provide(source=SqlAlchemyOutboxRepository, provides=OutboxCommandGateway)
    provider.provide(source=RetortEventSerializer, provides=EventSerializer)
    provider.provide(source=OutboxEventBus, provides=EventBus)

    provider.provide(source=SqlAlchemyCatalogQueryGateway, provides=CatalogQueryGateway)
    provider.provide(source=SqlAlchemyPricingGateway, provides=PricingGateway)
    provider.provide(
        source=projection_adapter.SqlAlchemyCatalogProjectionGateway,
        provides=CatalogProjectionGateway,
    )

    provider.provide(source=SqlAlchemyCartCommandGateway, provides=CartCommandGateway)
    provider.provide(source=SqlAlchemyCartQueryGateway, provides=CartQueryGateway)

    provider.provide(source=SqlAlchemyOrderCommandGateway, provides=OrderCommandGateway)
    provider.provide(source=SqlAlchemyOrderQueryGateway, provides=OrderQueryGateway)

    provider.provide(make_admin_registry, provides=AdminRegistry, scope=Scope.APP)
    provider.provide(
        make_default_price_type_id,
        provides=PriceTypeId,
        scope=Scope.APP,
    )

    return provider
