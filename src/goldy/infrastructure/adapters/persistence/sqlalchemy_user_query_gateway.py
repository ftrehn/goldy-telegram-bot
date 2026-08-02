import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, override
from uuid import UUID

from sqlalchemy import ColumnElement, String, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.application.common.views.user import MessengerAccountView, UserView
from goldy.infrastructure.errors import RepoError
from goldy.infrastructure.mappers.user_row_view_mapper import UserRowViewMapper
from goldy.infrastructure.persistence.models import (
    messenger_accounts_table,
    users_table,
)

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SqlAlchemyUserQueryGateway(UserQueryGateway):
    """DAO for the user read model.

    Selects the tables directly instead of loading aggregates: a page of the
    user list is going to be rendered, not reasoned about, and hydrating two
    hundred aggregates to print a table buys nothing.

    A page costs two round trips — the users, then their accounts in one
    ``IN`` — rather than a join that would repeat every user row once per
    linked platform and have to be de-duplicated in Python.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_row_view_mapper: UserRowViewMapper,
    ) -> None:
        self._session: Final[AsyncSession] = session
        self._mapper: Final[UserRowViewMapper] = user_row_view_mapper

    @override
    async def read_by_id(self, user_id: UserId) -> UserView | None:
        stmt = select(users_table).where(users_table.c.id == user_id)

        try:
            row = (await self._session.execute(stmt)).mappings().one_or_none()
        except SQLAlchemyError as e:
            logger.exception("failed to read the user view")
            msg = "Failed to read the user view."
            raise RepoError(msg) from e

        if row is None:
            return None

        accounts = await self._accounts_for([row["id"]])
        return self._mapper.to_view(row, accounts.get(row["id"], ()))

    @override
    async def read_all(
        self,
        pagination: Pagination,
        sorting: SortingOrder,
        filters: UserFilters,
    ) -> Sequence[UserView]:
        created_at = users_table.c.created_at
        order = created_at.desc() if sorting is SortingOrder.DESC else created_at.asc()

        stmt = select(users_table).where(*self._conditions(filters)).order_by(order)

        if pagination.limit is not None:
            stmt = stmt.limit(pagination.limit)
        if pagination.offset is not None:
            stmt = stmt.offset(pagination.offset)

        try:
            rows = (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read the user list")
            msg = "Failed to read the user list."
            raise RepoError(msg) from e

        if not rows:
            return []

        accounts = await self._accounts_for([row["id"] for row in rows])
        return [self._mapper.to_view(row, accounts.get(row["id"], ())) for row in rows]

    @override
    async def total(self, filters: UserFilters) -> int:
        stmt = (
            select(func.count())
            .select_from(users_table)
            .where(*self._conditions(filters))
        )

        try:
            return (await self._session.execute(stmt)).scalar_one()
        except SQLAlchemyError as e:
            logger.exception("failed to count users")
            msg = "Failed to count users."
            raise RepoError(msg) from e

    async def _accounts_for(
        self,
        user_ids: Sequence[UUID],
    ) -> dict[UUID, tuple[MessengerAccountView, ...]]:
        stmt = (
            select(messenger_accounts_table)
            .where(messenger_accounts_table.c.user_id.in_(user_ids))
            .order_by(messenger_accounts_table.c.linked_at)
        )

        try:
            rows = (await self._session.execute(stmt)).mappings().all()
        except SQLAlchemyError as e:
            logger.exception("failed to read the messenger accounts")
            msg = "Failed to read the messenger accounts."
            raise RepoError(msg) from e

        grouped: defaultdict[UUID, list[MessengerAccountView]] = defaultdict(list)

        for row in rows:
            grouped[row["user_id"]].append(self._mapper.to_account_view(row))

        return {user_id: tuple(views) for user_id, views in grouped.items()}

    def _conditions(self, filters: UserFilters) -> list[ColumnElement[bool]]:
        """Builds the WHERE clauses for the admin list.

        The phone number is cast to text before matching: its column carries a
        ``PhoneNumber``, so a bare search string would be handed to the type
        decorator as though it were one.
        """
        conditions: list[ColumnElement[bool]] = []

        if filters.role is not None:
            conditions.append(users_table.c.role == filters.role)

        if filters.status is not None:
            conditions.append(users_table.c.status == filters.status)

        if filters.search:
            pattern = f"%{filters.search}%"
            conditions.append(
                or_(
                    users_table.c.first_name.ilike(pattern),
                    users_table.c.last_name.ilike(pattern),
                    cast(users_table.c.phone_number, String).ilike(pattern),
                ),
            )

        return conditions
