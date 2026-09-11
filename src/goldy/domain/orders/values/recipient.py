from dataclasses import dataclass
from typing import override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.values.full_name import FullName
from goldy.domain.users.values.phone_number import PhoneNumber


@dataclass(frozen=True)
class Recipient(ValueObject):
    """Who will actually take the delivery.

    A field of the order rather than a reference to a ``User``, because the
    recipient need not be the buyer: ordering something for a parent is
    ordinary, and a reference would rewrite the past the moment that person
    edits their own profile.

    Not ``kw_only``: mapped as a SQLAlchemy ``composite`` over three columns,
    which is rebuilt positionally, so field order is part of the mapping.

    Three flat fields rather than a nested ``FullName``, because a composite
    inside a composite is not something SQLAlchemy handles well, while the
    phone column is an ordinary ``PhoneNumberType`` a composite works with
    normally. To avoid restating the name rules, validation builds a
    ``FullName`` and lets it raise its own error; :attr:`full_name` hands the
    same value back out.
    """

    first_name: str
    last_name: str | None
    phone_number: PhoneNumber

    @property
    def full_name(self) -> FullName:
        return FullName(self.first_name, self.last_name)

    @override
    def _validate(self) -> None:
        """Delegates the name rules to ``FullName`` rather than repeating them."""
        FullName(self.first_name, self.last_name)

    def __str__(self) -> str:
        return f"{self.full_name}, {self.phone_number}"
