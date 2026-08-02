from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.users.errors import EmptyFirstNameError, TooLongNamePartError

MAX_NAME_PART_LENGTH: Final[int] = 100


@dataclass(frozen=True)
class FullName(ValueObject):
    """What to call the person and what to put on the delivery slip.

    Only the first name is required: messengers do not guarantee a surname, and
    refusing to register someone over a missing one would be absurd.

    Not ``kw_only`` unlike the other value objects, because this one is mapped
    as a SQLAlchemy ``composite`` over two columns and SQLAlchemy rebuilds it
    positionally when loading a row. Field order is therefore part of the
    mapping — reordering these two silently swaps names in the database.
    """

    first_name: str
    last_name: str | None = None

    @override
    def _validate(self) -> None:
        if not self.first_name.strip():
            msg = "First name cannot be empty."
            raise EmptyFirstNameError(msg)

        for part in (self.first_name, self.last_name):
            if part is not None and len(part) > MAX_NAME_PART_LENGTH:
                msg = (
                    f"Name part cannot be longer than "
                    f"{MAX_NAME_PART_LENGTH} characters, got {len(part)}."
                )
                raise TooLongNamePartError(msg)

    def __str__(self) -> str:
        if self.last_name is None:
            return self.first_name
        return f"{self.first_name} {self.last_name}"
