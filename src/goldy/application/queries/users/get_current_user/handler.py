from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserQueryGateway
from goldy.application.common.views.user import UserView
from goldy.application.error import UserNotFoundError
from goldy.application.queries.users.get_current_user.query import GetCurrentUserQuery


class GetCurrentUserHandler(QueryHandler[GetCurrentUserQuery, UserView]):
    """Reads the caller's own profile.

    Goes through the query gateway rather than loading the aggregate: nothing
    here is going to be changed, and a view is what the screen wants anyway.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        user_query_gateway: UserQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._user_query_gateway: Final[UserQueryGateway] = user_query_gateway

    @override
    async def handle(self, query: GetCurrentUserQuery) -> UserView:
        user_id = await self._identity_provider.get_current_user_id()
        view = await self._user_query_gateway.read_by_id(user_id)

        if view is None:
            msg = f"User '{user_id}' does not exist."
            raise UserNotFoundError(msg)

        return view
