from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.users.entities.user import User
    from goldy.domain.users.values.external_account_id import ExternalAccountId
    from goldy.domain.users.values.messenger_platform import MessengerPlatform
    from goldy.domain.users.values.phone_number import PhoneNumber
    from goldy.domain.users.values.user_id import UserId


class UserCommandGateway(Protocol):
    """Write-side access to the :class:`User` aggregate.

    Always hands back whole aggregates, accounts included: the rules about
    linking are checked against the entire account list, so a partially loaded
    user could pass a check it should have failed.

    Three lookups rather than one because registration needs all three, and
    each answers a different question: "have I seen this account before",
    "have I seen this person before", "give me the user this command names".
    """

    @abstractmethod
    async def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def by_id(self, user_id: UserId) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def by_phone_number(self, phone_number: PhoneNumber) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def by_messenger_account(
        self,
        platform: MessengerPlatform,
        external_id: ExternalAccountId,
    ) -> User | None:
        raise NotImplementedError
