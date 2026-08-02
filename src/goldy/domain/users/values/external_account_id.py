from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import (
    EmptyExternalAccountIdError,
    TooLongExternalAccountIdError,
)

MAX_EXTERNAL_ACCOUNT_ID_LENGTH: Final[int] = 64


@dataclass(frozen=True, kw_only=True)
class ExternalAccountId(ValueObject):
    """The id a platform gave to one of its own accounts.

    Text rather than an integer even though Telegram's is numeric: MAX need not
    agree, and both end up in the same column. Unique only within its platform,
    which is why it never identifies a user on its own.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "External account id cannot be empty."
            raise EmptyExternalAccountIdError(msg)

        if len(self.value) > MAX_EXTERNAL_ACCOUNT_ID_LENGTH:
            msg = (
                f"External account id cannot be longer than "
                f"{MAX_EXTERNAL_ACCOUNT_ID_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongExternalAccountIdError(msg)

    def __str__(self) -> str:
        return self.value
