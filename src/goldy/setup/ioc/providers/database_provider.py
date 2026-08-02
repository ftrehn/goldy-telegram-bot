from typing import Final

from dishka import Provider, Scope
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.setup.ioc.providers.sqlalchemy_provider import (
    get_engine,
    get_session,
    get_sessionmaker,
)


def database_provider() -> Provider:
    """Engine and session factory per process, session per request.

    The session is what makes a request a unit of work: every gateway resolved
    for one update shares it, so the transaction pipeline commits all of them
    together or none.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.provide(get_engine, scope=Scope.APP)
    provider.provide(get_sessionmaker, scope=Scope.APP)
    provider.provide(get_session, provides=AsyncSession)
    return provider
