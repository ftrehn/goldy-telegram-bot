from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.query_params.user_filters import UserFilters
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.user import UserListView
from goldy.application.queries.users.list_users.query import ListUsersQuery
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.permission import IsStaff, StaffContext


class ListUsersHandler(QueryHandler[ListUsersQuery, UserListView]):
    """Reads a page of users for the admin side.

    Returns the unpaginated total alongside the page, because a pager that only
    knows the current slice cannot say how many pages there are.
    """

    def __init__(
        self,
        user_provider: UserProvider,
        user_query_gateway: UserQueryGateway,
        access_service: AccessService,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._user_query_gateway: Final[UserQueryGateway] = user_query_gateway
        self._access_service: Final[AccessService] = access_service

    @override
    async def handle(self, query: ListUsersQuery) -> UserListView:
        subject = await self._user_provider.current()
        self._access_service.authorize(
            IsStaff(),
            context=StaffContext(subject=subject),
        )

        filters = UserFilters(
            role=query.role,
            status=query.status,
            search=query.search,
        )
        users = await self._user_query_gateway.read_all(
            Pagination(limit=query.limit, offset=query.offset),
            query.sorting,
            filters,
        )
        total = await self._user_query_gateway.total(filters)

        return UserListView(users=tuple(users), total=total)
