import logging
from typing import TYPE_CHECKING, Final, override

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.error import UserAlreadyExistsError
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.users.entities.user import User
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.persistence.models import (
    messenger_accounts_table,
    users_table,
)

if TYPE_CHECKING:
    from goldy.domain.users.values.external_account_id import ExternalAccountId
    from goldy.domain.users.values.messenger_platform import MessengerPlatform
    from goldy.domain.users.values.phone_number import PhoneNumber
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyUserCommandGateway(UserCommandGateway):
    """Loads and stores :class:`User` aggregates.

    Every aggregate handed back gets the request-scoped ``EventsCollection``
    injected, because it is not a column and SQLAlchemy leaves it unset on
    loaded instances. Without it the first method that records an event would
    fail on a missing attribute — long after the load that actually caused it.
    """

    def __init__(
        self,
        session: AsyncSession,
        events_collection: EventsCollection,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._events_collection: Final[EventsCollection] = events_collection

    @override
    async def add(self, user: User) -> None:
        """Inserts a new user, flushing so a clash surfaces here.

        The flush is the point. Deferring it to commit would raise inside the
        transaction pipeline as a generic ``RepoError``, and the caller could
        no longer tell "somebody registered this number a millisecond ago" —
        which is retryable — from a broken database, which is not.
        """
        self._session.add(user)

        try:
            await self._session.flush()
        except IntegrityError as e:
            logger.info("user already exists: %s", user.id)
            msg = (
                f"Phone number '{user.phone_number}' or one of the messenger "
                f"accounts is already taken."
            )
            raise UserAlreadyExistsError(msg) from e
        except SQLAlchemyError as e:
            logger.exception("failed to add the user")
            msg = "Failed to add the user."
            raise RepoError(msg) from e

    @override
    async def by_id(self, user_id: UserId) -> User | None:
        try:
            user = await self._session.get(User, user_id)
        except SQLAlchemyError as e:
            logger.exception("failed to read the user by id")
            msg = "Failed to read the user by id."
            raise RepoError(msg) from e

        return self._inject(user) if user is not None else None

    @override
    async def by_phone_number(self, phone_number: PhoneNumber) -> User | None:
        stmt = select(User).where(users_table.c.phone_number == phone_number)
        return await self._one_or_none(stmt, "by phone number")

    @override
    async def by_messenger_account(
        self,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
    ) -> User | None:
        stmt = (
            select(User)
            .join(
                messenger_accounts_table,
                messenger_accounts_table.c.user_id == users_table.c.id,
            )
            .where(
                messenger_accounts_table.c.platform == platform,
                messenger_accounts_table.c.external_id == external_id,
            )
        )
        return await self._one_or_none(stmt, "by messenger account")

    async def _one_or_none(self, stmt: Select[tuple[User]], what: str) -> User | None:
        try:
            user = (await self._session.execute(stmt)).scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the user %s", what)
            msg = f"Failed to read the user {what}."
            raise RepoError(msg) from e

        return self._inject(user) if user is not None else None

    def _inject(self, user: User) -> User:
        user.events_collection = self._events_collection
        return user
