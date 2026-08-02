from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from goldy.domain.users.values.phone_number import PhoneNumber


class AdminRegistry(Protocol):
    """The numbers that are administrators by decree rather than by grant.

    A port rather than a config read inline, because the handlers that consult
    it have no business knowing whether the answer comes from an environment
    variable, a secrets store or a table — and because a test needs to say "this
    number is an admin" without touching the environment.
    """

    @abstractmethod
    def is_admin(self, phone_number: PhoneNumber) -> bool:
        raise NotImplementedError

    @abstractmethod
    def phone_numbers(self) -> Sequence[PhoneNumber]:
        """Everyone on the list, whether or not they have registered yet."""
        raise NotImplementedError
