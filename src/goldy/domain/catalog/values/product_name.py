from dataclasses import dataclass
from typing import Final, override
from unicodedata import category

from goldy.domain.catalog.errors import (
    EmptyProductNameError,
    MalformedProductNameError,
    TooLongProductNameError,
)
from goldy.domain.common.value_object import ValueObject

MAX_PRODUCT_NAME_LENGTH: Final[int] = 255
CONTROL_CHARACTER: Final[str] = "Cc"
"""The Unicode category of tabs, line feeds and the like — never part of a name."""


@dataclass(frozen=True, kw_only=True)
class ProductName(ValueObject):
    """What the product is called in the catalog.

    Comes from 1C and is copied into an order line as a snapshot, so it is the
    text the customer will still be shown months later when the catalog has
    moved on.

    The invariants are the ones a name has as a piece of text, no more. It is
    not empty, it fits the column, and it carries no control characters — a
    tab or a stray NUL in a name is always a broken export and never a
    product, and Telegram would render it as a hole in the message. There is
    deliberately no check on the *words*: the names are written by the shop's
    own staff in 1C, not typed by customers, so a profanity filter would be a
    rule against the people it is meant to protect.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Product name cannot be empty."
            raise EmptyProductNameError(msg)

        if len(self.value) > MAX_PRODUCT_NAME_LENGTH:
            msg = (
                f"Product name cannot be longer than "
                f"{MAX_PRODUCT_NAME_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongProductNameError(msg)

        if any(category(character) == CONTROL_CHARACTER for character in self.value):
            msg = "Product name contains control characters."
            raise MalformedProductNameError(msg)

    def __str__(self) -> str:
        return self.value
