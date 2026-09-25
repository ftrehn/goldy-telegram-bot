import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Final, override

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from goldy.application.common.ports.catalog import CatalogSyncLock
from goldy.infrastructure.errors import RepoError

logger: Final[logging.Logger] = logging.getLogger(__name__)

CATALOG_SYNC_LOCK_KEY: Final[int] = 0x676F6C6479_0001
"""The advisory lock's key: ``goldy`` in ASCII plus a number for this lock.

Advisory keys are one 64-bit namespace per database, shared with anything else
that takes advisory locks there. A spelled-out constant, rather than a hash of
a name computed at runtime, is what anybody reading ``pg_locks`` can match.
"""

_TRY_LOCK: Final = text("SELECT pg_try_advisory_lock(:key)")
_UNLOCK: Final = text("SELECT pg_advisory_unlock(:key)")


class PostgresCatalogSyncLock(CatalogSyncLock):
    """The pass lock as a Postgres session-level advisory lock.

    Session-level, not transaction-level, and on a connection of its own. A
    pass is dozens of transactions — one per batch, each committed as it goes
    — so a transaction-scoped lock would be gone after the first commit. The
    connection is checked out of the pool for the whole pass and nothing else
    runs on it; the lock belongs to its backend session.

    Postgres is the one thing every worker, every scheduler replica and the
    seeder already share, and a lock held by a session dies with it: a worker
    killed mid-pass loses its connection, the server ends the session and the
    lock is gone, with no expiry to tune and no stale key to clean up by hand.

    The connection goes back to the pool only unlocked. If the unlock itself
    fails the connection is invalidated instead, which closes the backend
    session and releases the lock with it — a pooled connection still holding
    the lock would block every later pass until the process restarted.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine: Final[AsyncEngine] = engine

    @override
    @asynccontextmanager
    async def hold(self) -> AsyncIterator[bool]:
        connection = await self._connect()
        acquired = False
        try:
            acquired = await self._try_lock(connection)
            yield acquired
        finally:
            await self._release(connection, acquired=acquired)

    async def _connect(self) -> AsyncConnection:
        try:
            return await self._engine.connect()
        except SQLAlchemyError as e:
            logger.exception("catalog sync lock: no connection")
            msg = "Cannot open a connection to take the catalog sync lock."
            raise RepoError(msg) from e

    async def _try_lock(self, connection: AsyncConnection) -> bool:
        try:
            result = await connection.execute(_TRY_LOCK, {"key": CATALOG_SYNC_LOCK_KEY})
            acquired = bool(result.scalar_one())
            await connection.commit()
        except SQLAlchemyError as e:
            logger.exception("catalog sync lock: try-lock failed")
            msg = "Cannot ask Postgres for the catalog sync lock."
            raise RepoError(msg) from e
        return acquired

    @staticmethod
    async def _release(connection: AsyncConnection, *, acquired: bool) -> None:
        """Unlocks and returns the connection; invalidates it if unlocking fails.

        Never raises: it runs in ``finally``, and an error here would replace
        whatever the pass itself raised — the one error worth reading.
        """
        try:
            if acquired:
                await connection.execute(_UNLOCK, {"key": CATALOG_SYNC_LOCK_KEY})
                await connection.commit()
        except SQLAlchemyError:
            logger.exception("catalog sync lock: unlock failed, dropping the session")
            with suppress(SQLAlchemyError):
                await connection.invalidate()

        try:
            await connection.close()
        except SQLAlchemyError:
            logger.exception("catalog sync lock: the connection did not close cleanly")
