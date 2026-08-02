import re
from dataclasses import dataclass
from typing import Final, Self, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import (
    EmptyPhoneNumberError,
    InvalidPhoneNumberFormatError,
)

_DIGITS: Final[re.Pattern[str]] = re.compile(r"\D")
_E164: Final[re.Pattern[str]] = re.compile(r"^\+[1-9]\d{7,14}$")

_RUSSIAN_TRUNK_PREFIX: Final[str] = "8"
_RUSSIAN_COUNTRY_CODE: Final[str] = "+7"
_RUSSIAN_NATIONAL_LENGTH: Final[int] = 11


@dataclass(frozen=True, kw_only=True)
class PhoneNumber(ValueObject):
    """A subscriber's number in canonical E.164 form, ``+<country><number>``.

    This is the identity of a person in the system: two messenger accounts are
    recognised as the same human because their numbers compare equal. So the
    constructor accepts nothing but the canonical form — one number reaching
    storage as ``89991234567`` and another as ``+79991234567`` would silently
    become two people.

    Whatever a platform actually hands over goes through :meth:`from_raw`.
    """

    value: str

    @classmethod
    def from_raw(cls, raw: str) -> Self:
        """Normalises whatever the messenger gave us into E.164.

        Telegram sends ``79991234567``, a person typing by hand sends
        ``8 (999) 123-45-67``; both name the same subscriber.

        Raises:
            EmptyPhoneNumberError: ``raw`` holds no digits at all.
            InvalidPhoneNumberFormatError: the result is not a valid number.
        """
        digits: str = _DIGITS.sub("", raw)

        if not digits:
            msg = "Phone number cannot be empty."
            raise EmptyPhoneNumberError(msg)

        explicit_country_code: bool = raw.lstrip().startswith("+")

        if (
            not explicit_country_code
            and len(digits) == _RUSSIAN_NATIONAL_LENGTH
            and digits.startswith(_RUSSIAN_TRUNK_PREFIX)
        ):
            return cls(value=_RUSSIAN_COUNTRY_CODE + digits[1:])

        return cls(value="+" + digits)

    @override
    def _validate(self) -> None:
        if not self.value:
            msg = "Phone number cannot be empty."
            raise EmptyPhoneNumberError(msg)

        if not _E164.fullmatch(self.value):
            msg = (
                f"Phone number {self.value!r} is not in E.164 format "
                f"(expected '+' followed by 8 to 15 digits)."
            )
            raise InvalidPhoneNumberFormatError(msg)

    def __str__(self) -> str:
        return self.value
