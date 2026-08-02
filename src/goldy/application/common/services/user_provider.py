from typing import Final, final

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.error import UserNotFoundError
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.user_id import UserId


@final
class UserProvider:
    """Loads user aggregates for command handlers.

    Turns "the gateway returned None" into a raised error once, here, rather
    than in every handler: a handler that forgot the check would carry a
    ``None`` into the domain and fail somewhere far less obvious.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        user_command_gateway: UserCommandGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._user_command_gateway: Final[UserCommandGateway] = user_command_gateway

    async def current(self) -> User:
        """The person running this command.

        Raises:
            UserNotFoundError: they were removed between the update arriving
                and the command running.
        """
        return await self.by_id(await self._identity_provider.get_current_user_id())

    async def by_id(self, user_id: UserId) -> User:
        """The person a command names.

        Raises:
            UserNotFoundError: no such user.
        """
        user = await self._user_command_gateway.by_id(user_id)

        if user is None:
            msg = f"User '{user_id}' does not exist."
            raise UserNotFoundError(msg)

        return user
