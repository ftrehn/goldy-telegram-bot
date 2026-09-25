"""The pass lock's own decisions: what it releases, and what it never raises.

The lock itself is Postgres's. What is ours is the bookkeeping around it: the
connection goes back to the pool only unlocked, a failed unlock drops the
session instead (which releases the lock server-side), a failure of the pass
is never replaced by a failure of the release, and a database that cannot be
reached is a ``RepoError`` rather than a SQLAlchemy exception.
"""

import pytest

from goldy.infrastructure.adapters.persistence.postgres_catalog_sync_lock import (
    PostgresCatalogSyncLock,
)
from goldy.infrastructure.errors import RepoError
from tests.unit.stubs.persistence import LockConnection, LockEngine


class PassFailedError(Exception):
    """What the pass inside the lock raised, standing in for any error."""


async def test_a_granted_lock_is_unlocked_before_the_connection_goes_back() -> None:
    connection = LockConnection(lock_granted=True)
    lock = PostgresCatalogSyncLock(LockEngine(connection).as_engine())

    async with lock.hold() as acquired:
        assert acquired

    assert connection.unlocked
    assert connection.closed


async def test_a_lock_held_elsewhere_is_reported_and_never_unlocked() -> None:
    """Unlocking a lock this session does not hold only earns a Postgres warning."""
    connection = LockConnection(lock_granted=False)
    lock = PostgresCatalogSyncLock(LockEngine(connection).as_engine())

    async with lock.hold() as acquired:
        assert not acquired

    assert not connection.unlocked
    assert connection.closed


async def test_a_pass_that_fails_still_releases_and_its_error_is_the_one_raised() -> None:
    connection = LockConnection(lock_granted=True)
    lock = PostgresCatalogSyncLock(LockEngine(connection).as_engine())

    with pytest.raises(PassFailedError):
        async with lock.hold():
            raise PassFailedError

    assert connection.unlocked
    assert connection.closed


async def test_a_failed_unlock_drops_the_session_instead_of_pooling_it() -> None:
    """A pooled connection still holding the lock would block every later pass."""
    connection = LockConnection(lock_granted=True, fail_unlock=True)
    lock = PostgresCatalogSyncLock(LockEngine(connection).as_engine())

    async with lock.hold():
        pass

    assert connection.invalidated
    assert connection.closed


async def test_a_database_that_cannot_be_reached_is_a_repo_error() -> None:
    lock = PostgresCatalogSyncLock(LockEngine(connection=None).as_engine())

    with pytest.raises(RepoError):
        async with lock.hold():
            pass
