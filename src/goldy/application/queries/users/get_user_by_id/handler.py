from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.user import UserView
from goldy.application.error import UserNotFoundError
from goldy.application.queries.users.get_user_by_id.query import GetUserByIdQuery
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.permission import IsStaff, StaffContext
from goldy.domain.users.values.user_id import UserId


class GetUserByIdHandler(QueryHandler[GetUserByIdQuery, UserView]):
    """Reads anyone's card, for staff only.

    Guarded by ``IsStaff`` rather than ``CanManageSubordinate``: reading a
    colleague's card is how staff coordinate, while acting on them is not.
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
    async def handle(self, query: GetUserByIdQuery) -> UserView:
        subject = await self._user_provider.current()
        self._access_service.authorize(
            IsStaff(),
            context=StaffContext(subject=subject),
        )

        user_id = UserId(query.user_id)
        view = await self._user_query_gateway.read_by_id(user_id)

        if view is None:
            msg = f"User '{user_id}' does not exist."
            raise UserNotFoundError(msg)

        return view
