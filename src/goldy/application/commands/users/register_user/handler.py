import logging
from typing import Final, override

from goldy.application.commands.users.register_user.command import RegisterUserCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.admin_registry import AdminRegistry
from goldy.application.common.ports.mappers import UserViewMapper
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.common.views.user import UserView
from goldy.domain.users.entities.messenger_account import MessengerAccount
from goldy.domain.users.factories.user_factory import UserFactory
from goldy.domain.users.registration import Registration
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.locale import Locale
from goldy.domain.users.values.messenger_username import MessengerUsername
from goldy.domain.users.values.phone_number import PhoneNumber
from goldy.domain.users.values.user_role import UserRole

logger: Final[logging.Logger] = logging.getLogger(__name__)


class RegisterUserHandler(CommandHandler[RegisterUserCommand, UserView]):
    """Resolves an incoming contact to a user, creating one only if needed.

    Three outcomes, checked in this order:

    1. **This account is known.** A repeated ``/start``. Refresh the handle and
       return — creating a second user here would be the commonest bug in the
       whole flow.
    2. **This number is known, from another platform.** The same human arriving
       from MAX after Telegram, so their new account joins the user who already
       owns the number. Safe only because the platform vouched for the number.
    3. **Neither is known.** A genuinely new person.

    Two simultaneous first messages both reach step 3 and both insert; the
    unique indexes reject the loser, which surfaces as
    ``UserAlreadyExistsError`` and is worth one retry — the retry lands in step
    1 or 2 and succeeds.
    """

    def __init__(
        self,
        user_command_gateway: UserCommandGateway,
        user_factory: UserFactory,
        user_view_mapper: UserViewMapper,
        admin_registry: AdminRegistry,
    ) -> None:
        self._user_command_gateway: Final[UserCommandGateway] = user_command_gateway
        self._user_factory: Final[UserFactory] = user_factory
        self._user_view_mapper: Final[UserViewMapper] = user_view_mapper
        self._admin_registry: Final[AdminRegistry] = admin_registry

    @override
    async def handle(self, command: RegisterUserCommand) -> UserView:
        external_id = ExternalAccountId(value=command.external_id)
        username = (
            None
            if command.username is None
            else MessengerUsername(value=command.username)
        )

        known_account = await self._user_command_gateway.by_messenger_account(
            command.platform,
            external_id,
        )
        if known_account is not None:
            known_account.refresh_username(command.platform, username)
            logger.debug("register_user: %s is already known", known_account.id)
            return self._user_view_mapper.to_view(known_account)

        phone_number = PhoneNumber.from_raw(command.phone_number)

        known_person = await self._user_command_gateway.by_phone_number(phone_number)
        if known_person is not None:
            known_person.link_account(
                MessengerAccount(
                    platform=command.platform,
                    external_id=external_id,
                    username=username,
                ),
            )
            logger.info(
                "register_user: linked %s to existing user %s",
                command.platform.value,
                known_person.id,
            )
            return self._user_view_mapper.to_view(known_person)

        user = self._user_factory.create(
            Registration(
                phone_number=phone_number,
                full_name=FullName(
                    first_name=command.first_name,
                    last_name=command.last_name,
                ),
                account=MessengerAccount(
                    platform=command.platform,
                    external_id=external_id,
                    username=username,
                ),
                locale=Locale.from_language_code(command.language_code),
            ),
        )
        # Checked here as well as at startup: a number added to the list while
        # its owner had not registered yet would otherwise wait for a restart,
        # and an administrator who has to wait for one looks like a bug.
        if self._admin_registry.is_admin(phone_number):
            user.assign_role(UserRole.ADMIN)
            logger.info("register_user: %s is a configured admin", user.id)

        await self._user_command_gateway.add(user)
        logger.info("register_user: registered new user %s", user.id)
        return self._user_view_mapper.to_view(user)
