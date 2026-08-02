import logging
from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from goldy.setup.configs.alchemy_config import SQLAlchemyConfig
from goldy.setup.configs.postgres_config import PostgresConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def get_engine(
    postgres_config: PostgresConfig,
    alchemy_config: SQLAlchemyConfig,
) -> AsyncIterator[AsyncEngine]:
    """Creates the engine and disposes it when the process ends."""
    engine: AsyncEngine = create_async_engine(
        postgres_config.uri,
        echo=alchemy_config.echo,
        pool_size=alchemy_config.pool_size,
        max_overflow=alchemy_config.max_overflow,
        pool_pre_ping=alchemy_config.pool_pre_ping,
        pool_recycle=alchemy_config.pool_recycle,
        future=alchemy_config.future,
    )
    logger.debug("Async engine created")
    yield engine
    logger.debug("Disposing async engine...")
    await engine.dispose()


def get_sessionmaker(
    engine: AsyncEngine,
    alchemy_config: SQLAlchemyConfig,
) -> async_sessionmaker[AsyncSession]:
    """Builds the session factory once per process."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=alchemy_config.auto_flush,
        expire_on_commit=alchemy_config.expire_on_commit,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One session per request, closed however the request ends.

    Closed in a ``finally`` rather than an ``async with``: the generator may be
    discarded without being resumed, and a context manager wrapped around the
    yield would then never run its exit.
    """
    session: AsyncSession = session_factory()
    try:
        yield session
    finally:
        await session.close()
