import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Final, override

from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.users import UserCommandGateway
from goldy.application.error import AuthenticationError

if TYPE_CHECKING:
    from goldy.domain.users.values.external_account_id import ExternalAccountId
    from goldy.domain.users.values.messenger_platform import MessengerPlatform
    from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class MessengerIdentityProvider(IdentityProvider):
    """Resolves the account writing to us into our own ``UserId``.

    The lookup is the same on every platform — only where the account id comes
    from differs — so it lives here once and each platform supplies the two
    missing pieces. Exactly one subclass is bound per process by dishka: the
    Telegram worker never constructs the MAX one.
    """

    def __init__(self, user_command_gateway: UserCommandGateway) -> None:
        self._user_command_gateway: Final[UserCommandGateway] = user_command_gateway

    @property
    @abstractmethod
    def platform(self) -> MessengerPlatform:
        """Which messenger this process serves."""
        raise NotImplementedError

    @abstractmethod
    async def current_external_id(self) -> ExternalAccountId:
        """The account id carried by the update being handled."""
        raise NotImplementedError

    @override
    async def get_current_user_id(self) -> UserId:
        """The user behind the update.

        Raises:
            AuthenticationError: nobody owns this account yet, which is the
                normal state of anyone who has not shared their contact.
                Presentation is expected to answer with the registration
                prompt rather than an error.
        """
        external_id = await self.current_external_id()
        user = await self._user_command_gateway.by_messenger_account(
            self.platform,
            external_id,
        )

        if user is None:
            logger.info(
                "identity: unregistered %s account %s",
                self.platform.value,
                external_id,
            )
            msg = f"No user is linked to {self.platform.value} account '{external_id}'."
            raise AuthenticationError(msg)

        return user.id
