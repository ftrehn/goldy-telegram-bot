import logging
from typing import Final, final, override

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.error import AuthenticationError
from goldy.domain.users.values.external_account_id import ExternalAccountId
from goldy.domain.users.values.messenger_platform import MessengerPlatform
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class TelegramIdentityProvider(IdentityProvider):
    """Resolves the Telegram account writing to us into our own ``UserId``.

    Deliberately flat rather than a subclass of some shared messenger base: the
    lookup is six lines, and MAX will not share the interesting parts — what
    counts as "no user" differs per platform, and a template method would force
    both into whichever shape was written first.

    The account id is pulled out of the update by the container, not here:
    aiogram already put it in the middleware data, and reaching for aiogram
    types in infrastructure would drag the framework a layer too deep.
    """

    def __init__(
        self,
        external_id: ExternalAccountId | None,
        user_command_gateway: UserCommandGateway,
    ) -> None:
        self._external_id: Final[ExternalAccountId | None] = external_id
        self._user_command_gateway: Final[UserCommandGateway] = user_command_gateway

    @override
    async def get_current_user_id(self) -> UserId:
        """The user behind the update.

        Raises:
            AuthenticationError: the update carried no user at all — a channel
                post, say — or the account writing to us belongs to nobody yet.
                Both are things Telegram legitimately sends, so neither is a
                crash; the gate turns them into an invitation to register.
        """
        if self._external_id is None:
            msg = "This update carries no Telegram user."
            raise AuthenticationError(msg)

        user = await self._user_command_gateway.by_messenger_account(
            MessengerPlatform.TELEGRAM,
            self._external_id,
        )

        if user is None:
            logger.info("identity: unregistered telegram account %s", self._external_id)
            msg = f"No user is linked to Telegram account '{self._external_id}'."
            raise AuthenticationError(msg)

        return user.id
