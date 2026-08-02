from typing import Final, override

from goldy.application.commands.users.unlink_messenger_account.command import (
    UnlinkMessengerAccountCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.mappers import UserViewMapper
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.user import UserView
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.composite import AnyOf
from goldy.domain.users.services.authorization.permission import (
    CanManageSelf,
    CanManageSubordinate,
    UserManagementContext,
)
from goldy.domain.users.values.user_id import UserId


class UnlinkMessengerAccountHandler(
    CommandHandler[UnlinkMessengerAccountCommand, UserView],
):
    """Detaches a platform, unless it is the only way left to reach them."""

    def __init__(
        self,
        user_provider: UserProvider,
        access_service: AccessService,
        user_view_mapper: UserViewMapper,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._access_service: Final[AccessService] = access_service
        self._user_view_mapper: Final[UserViewMapper] = user_view_mapper

    @override
    async def handle(self, command: UnlinkMessengerAccountCommand) -> UserView:
        subject = await self._user_provider.current()
        target = await self._user_provider.by_id(UserId(command.user_id))

        self._access_service.authorize(
            AnyOf(CanManageSelf(), CanManageSubordinate()),
            context=UserManagementContext(subject=subject, target=target),
        )

        target.unlink_account(command.platform)
        return self._user_view_mapper.to_view(target)
