from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId


class IdentityProvider(Protocol):
    """Who is running the current command.

    Returns our own ``UserId``, never a platform id: a handler reasoning in
    ``telegram_id`` would stop recognising the same person the moment they
    wrote from MAX. Resolving a platform account to a user happens once, in the
    adapter behind this port.

    One implementation per platform, bound by dishka according to which process
    is running — the Telegram worker never constructs the MAX one.
    """

    @abstractmethod
    async def get_current_user_id(self) -> UserId:
        """The user behind the update being handled.

        Raises:
            AuthenticationError: the account writing to us belongs to nobody —
                they have not registered yet.
        """
        raise NotImplementedError
