from typing import Final

from dishka import Provider, Scope

from goldy.application.common.ports.mappers import UserViewMapper
from goldy.infrastructure.mappers.adaptix_user_view_mapper import AdaptixUserViewMapper
from goldy.infrastructure.mappers.sqlalchemy_user_row_view_mapper import (
    SqlAlchemyUserRowViewMapper,
)
from goldy.infrastructure.mappers.user_row_view_mapper import UserRowViewMapper


def mappers_provider() -> Provider:
    """Binds every mapping port to the adapter that performs it.

    ``APP`` scope, unlike the gateways: a mapper holds no session and no events
    collection, and the adaptix converters it calls are compiled once at import
    time. Rebuilding one per update would allocate for nothing.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.provide(source=AdaptixUserViewMapper, provides=UserViewMapper)
    provider.provide(source=SqlAlchemyUserRowViewMapper, provides=UserRowViewMapper)
    return provider
