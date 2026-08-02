from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import (
    EmptyMessengerUsernameError,
    TooLongMessengerUsernameError,
)

MAX_MESSENGER_USERNAME_LENGTH: Final[int] = 64


@dataclass(frozen=True, kw_only=True)
class MessengerUsername(ValueObject):
    """The ``@handle`` an account currently shows.

    Owned by the platform and changeable there at any moment, so it is kept for
    support staff to search by and never used to identify anyone. An account
    without a handle is modelled as no ``MessengerUsername`` at all rather than
    an empty one.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Messenger username cannot be empty."
            raise EmptyMessengerUsernameError(msg)

        if len(self.value) > MAX_MESSENGER_USERNAME_LENGTH:
            msg = (
                f"Messenger username cannot be longer than "
                f"{MAX_MESSENGER_USERNAME_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongMessengerUsernameError(msg)

    def __str__(self) -> str:
        return self.value
