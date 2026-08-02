from typing import Final, override

from goldy.application.commands.users.change_notification_preferences.command import (
    ChangeNotificationPreferencesCommand,
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


class ChangeNotificationPreferencesHandler(
    CommandHandler[ChangeNotificationPreferencesCommand, UserView],
):
    """Repoints notifications, if the target platform is actually linked."""

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
    async def handle(
        self,
        command: ChangeNotificationPreferencesCommand,
    ) -> UserView:
        subject = await self._user_provider.current()
        target = await self._user_provider.by_id(UserId(command.user_id))

        self._access_service.authorize(
            AnyOf(CanManageSelf(), CanManageSubordinate()),
            context=UserManagementContext(subject=subject, target=target),
        )

        # Derived from what they already have rather than built fresh: a new
        # ``UserPreferences`` would reset the language every time somebody
        # touched their notification channel.
        target.change_preferences(
            target.preferences.with_notify_via(command.notify_via).with_marketing_consent(
                consent=command.marketing_consent,
            ),
        )
        return self._user_view_mapper.to_view(target)
