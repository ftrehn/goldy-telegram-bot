import logging
from typing import Final, override

from goldy.application.commands.users.seed_admins.command import SeedAdminsCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.admin_registry import AdminRegistry
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.common.views.user import SeedAdminsResponse
from goldy.domain.users.values.user_role import UserRole

logger: Final[logging.Logger] = logging.getLogger(__name__)


class SeedAdminsHandler(CommandHandler[SeedAdminsCommand, SeedAdminsResponse]):
    """Promotes the configured numbers that already belong to someone.

    Goes through the aggregate rather than an UPDATE, so the promotion records
    a ``UserRoleChanged`` like any other and the audit trail does not have a
    hole where the administrators came from.

    No authorization check: nobody ran this command. It is the boundary
    condition the permission system cannot express, which is exactly why the
    list lives in configuration and not in the bot.
    """

    def __init__(
        self,
        user_command_gateway: UserCommandGateway,
        admin_registry: AdminRegistry,
    ) -> None:
        self._user_command_gateway: Final[UserCommandGateway] = user_command_gateway
        self._admin_registry: Final[AdminRegistry] = admin_registry

    @override
    async def handle(self, command: SeedAdminsCommand) -> SeedAdminsResponse:
        granted = 0
        already = 0
        pending = 0

        for phone_number in self._admin_registry.phone_numbers():
            user = await self._user_command_gateway.by_phone_number(phone_number)

            if user is None:
                logger.info(
                    "seed_admins: %s has not registered yet",
                    phone_number,
                )
                pending += 1
                continue

            if user.role is UserRole.ADMIN:
                already += 1
                continue

            user.assign_role(UserRole.ADMIN)
            granted += 1
            logger.info("seed_admins: granted admin to %s", user.id)

        log = logger.info if granted else logger.debug
        log(
            "seed_admins: granted=%d already=%d pending=%d",
            granted,
            already,
            pending,
        )
        return SeedAdminsResponse(granted=granted, already=already, pending=pending)
