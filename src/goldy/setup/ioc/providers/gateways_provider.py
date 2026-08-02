from typing import Final

from dishka import Provider, Scope

from goldy.application.common.ports.admin_registry import AdminRegistry
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
from goldy.infrastructure.adapters.auth.static_admin_registry import StaticAdminRegistry
from goldy.infrastructure.adapters.outbox.outbox_event_bus import OutboxEventBus
from goldy.infrastructure.adapters.outbox.retort_event_serializer import (
    RetortEventSerializer,
)
from goldy.infrastructure.adapters.persistence.sqlalchemy_outbox_command_gateway import (
    SqlAlchemyOutboxRepository,
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


def make_admin_registry(admin_config: AdminConfig) -> AdminRegistry:
    """Parses the configured numbers once, at startup.

    Built here rather than injected as a config, so the adapter never has to
    import ``setup`` — infrastructure depending on the composition root is how
    a project ends up unable to test either.
    """
    return StaticAdminRegistry.from_raw(admin_config.phone_numbers)


def gateways_provider() -> Provider:
    """Binds every application port to the adapter that implements it.

    ``REQUEST`` scope for everything built around the session or the events
    collection. The admin registry is the exception: it is a parsed list that
    cannot change while the process runs.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)

    provider.provide(source=SqlAlchemyTransactionManager, provides=TransactionManager)
    provider.provide(source=SqlAlchemyUserCommandGateway, provides=UserCommandGateway)
    provider.provide(source=SqlAlchemyUserQueryGateway, provides=UserQueryGateway)

    provider.provide(source=SqlAlchemyOutboxRepository, provides=OutboxCommandGateway)
    provider.provide(source=RetortEventSerializer, provides=EventSerializer)
    provider.provide(source=OutboxEventBus, provides=EventBus)

    provider.provide(make_admin_registry, provides=AdminRegistry, scope=Scope.APP)

    return provider
