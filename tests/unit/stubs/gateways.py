"""In-memory stand-ins for the user gateways.

They store aggregates by identity and hand back the *same* object, which mirrors
an identity-mapped session: a handler that reads an aggregate and mutates it
does not need to write it back for the change to be visible.
"""

from collections.abc import Sequence
from typing import final, override

from goldy.application.common.ports.users import (
    UserCommandGateway,
    UserQueryGateway,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.application.common.views.user import UserView
from goldy.application.error import UserAlreadyExistsError
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_id import UserId


@final
class InMemoryUserCommandGateway(UserCommandGateway):
    """Stands in for the write-side gateway, unique indexes included.

    ``add`` rejects a duplicate phone number or account the way the database
    does, because that rejection is the only thing standing between two
    simultaneous registrations and a person split in half.
    """

    def __init__(self) -> None:
        self.users: dict[UserId, User] = {}
        self.added: list[UserId] = []

    @override
    async def add(self, user: User) -> None:
        if await self.by_phone_number(user.phone_number) is not None:
            msg = f"Phone number '{user.phone_number}' is already taken."
            raise UserAlreadyExistsError(msg)

        for account in user.accounts:
            taken = await self.by_messenger_account(
                account.platform,
                account.external_id,
            )
            if taken is not None:
                msg = f"Account '{account.external_id}' is already taken."
                raise UserAlreadyExistsError(msg)

        self.users[user.id] = user
        self.added.append(user.id)

    @override
    async def by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    @override
    async def by_phone_number(self, phone_number: PhoneNumber) -> User | None:
        return next(
            (user for user in self.users.values() if user.phone_number == phone_number),
            None,
        )

    @override
    async def by_messenger_account(
        self,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
    ) -> User | None:
        return next(
            (
                user
                for user in self.users.values()
                if user.has_account(platform, external_id)
            ),
            None,
        )


@final
class InMemoryUserQueryGateway(UserQueryGateway):
    """Stands in for the read-side DAO, filtering in Python.

    The production gateway pushes this into SQL; written out here so a test can
    state the expected page directly.
    """

    def __init__(self) -> None:
        self.views: dict[UserId, UserView] = {}

    @override
    async def read_by_id(self, user_id: UserId) -> UserView | None:
        return self.views.get(user_id)

    @override
    async def read_all(
        self,
        pagination: Pagination,
        sorting: SortingOrder,
        filters: UserFilters,
    ) -> Sequence[UserView]:
        matching = sorted(
            self._matching(filters),
            key=lambda view: view.created_at,
            reverse=sorting is SortingOrder.DESC,
        )
        window = matching[pagination.offset or 0 :]

        if pagination.limit is not None:
            window = window[: pagination.limit]

        return window

    @override
    async def total(self, filters: UserFilters) -> int:
        return len(self._matching(filters))

    def _matching(self, filters: UserFilters) -> list[UserView]:
        views = list(self.views.values())

        if filters.role is not None:
            views = [view for view in views if view.role == filters.role.value]

        if filters.status is not None:
            views = [view for view in views if view.status == filters.status.value]

        if filters.search:
            needle = filters.search.lower()
            views = [view for view in views if needle in view.first_name.lower()]

        return views
