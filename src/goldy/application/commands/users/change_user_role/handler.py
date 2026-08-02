from typing import Final, override

from goldy.application.commands.users.change_user_role.command import (
    ChangeUserRoleCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.mappers import UserViewMapper
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.user import UserView
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.permission import (
    CanManageRole,
    CanManageSubordinate,
    RoleManagementContext,
    UserManagementContext,
)
from goldy.domain.users.values.user_id import UserId


class ChangeUserRoleHandler(CommandHandler[ChangeUserRoleCommand, UserView]):
    """Grants a role, checked from both ends.

    Two separate questions, and passing one does not imply the other: may the
    caller act on *this person* at all, and may they hand out *this role*.
    Without the second, a manager could promote a customer to manager and
    quietly manufacture a peer.
    """

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
    async def handle(self, command: ChangeUserRoleCommand) -> UserView:
        subject = await self._user_provider.current()
        target = await self._user_provider.by_id(UserId(command.user_id))

        self._access_service.authorize(
            CanManageSubordinate(),
            context=UserManagementContext(subject=subject, target=target),
        )
        self._access_service.authorize(
            CanManageRole(),
            context=RoleManagementContext(subject=subject, target_role=command.role),
        )

        target.assign_role(command.role)
        return self._user_view_mapper.to_view(target)
