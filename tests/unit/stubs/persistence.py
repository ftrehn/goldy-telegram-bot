"""A session that fails the way a database failing mid-request fails.

Every persistence adapter promises that no SQLAlchemy exception leaves it, and
that promise is the only reason handlers can catch ``AppError`` and mean it.
This stub is what makes the promise testable without a database: it answers
every call an adapter makes with the error a dropped connection produces.

``OperationalError`` rather than a bare ``SQLAlchemyError`` on purpose. The
adapters catch the base class, and a test raising the base class would not
notice if one of them were narrowed to a specific subclass one day.
"""

from typing import Final, cast, final

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

CONNECTION_LOST: Final[str] = "server closed the connection unexpectedly"


def _failure() -> OperationalError:
    return OperationalError("SELECT 1", (), Exception(CONNECTION_LOST))


@final
class FailingSession:
    """Stands in for :class:`AsyncSession` and refuses everything asked of it.

    Not a subclass. ``AsyncSession`` builds a real session state in its
    constructor, and overriding half of it to raise would test more of
    SQLAlchemy than of us; what an adapter needs from a session is the four
    methods below, and a stub owes it nothing else.
    """

    def __init__(self) -> None:
        self.added: list[object] = []

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise _failure()

    async def get(self, *_args: object, **_kwargs: object) -> object:
        raise _failure()

    async def flush(self, *_args: object, **_kwargs: object) -> None:
        raise _failure()

    def add(self, instance: object) -> None:
        """Records the aggregate, because only the flush after it may fail."""
        self.added.append(instance)


def failing_session() -> AsyncSession:
    """The stub under the type an adapter's constructor asks for."""
    return cast("AsyncSession", FailingSession())


@final
class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value


@final
class LockConnection:
    """Stands in for the ``AsyncConnection`` the advisory lock is held on.

    Answers ``pg_try_advisory_lock`` with ``lock_granted`` and records the
    statements it saw, so a test can tell an unlock from a bare close. Setting
    ``fail_unlock`` makes the unlock fail the way a dropped connection does.
    """

    def __init__(self, *, lock_granted: bool = True, fail_unlock: bool = False) -> None:
        self.lock_granted = lock_granted
        self.fail_unlock = fail_unlock
        self.statements: list[str] = []
        self.invalidated = False
        self.closed = False

    async def execute(self, statement: object, _params: object = None) -> _ScalarResult:
        sql = str(statement)
        self.statements.append(sql)
        if "unlock" in sql and self.fail_unlock:
            raise _failure()
        return _ScalarResult(self.lock_granted)

    async def commit(self) -> None:
        return None

    async def invalidate(self) -> None:
        self.invalidated = True

    async def close(self) -> None:
        self.closed = True

    @property
    def unlocked(self) -> bool:
        return any("pg_advisory_unlock" in sql for sql in self.statements)


@final
class LockEngine:
    """Hands out one :class:`LockConnection`, or fails to connect at all."""

    def __init__(self, connection: LockConnection | None = None) -> None:
        self.connection = connection

    async def connect(self) -> LockConnection:
        if self.connection is None:
            raise _failure()
        return self.connection

    def as_engine(self) -> AsyncEngine:
        return cast("AsyncEngine", self)
