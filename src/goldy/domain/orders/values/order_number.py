import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Self, override
from uuid import UUID

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import (
    EmptyOrderNumberError,
    InvalidOrderNumberFormatError,
)

CROCKFORD_ALPHABET: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Base 32 without ``I``, ``L``, ``O`` and ``U``.

Chosen for reading a number out over the phone: no letter looks like a digit,
and no letter is confused with another when spoken. Upper case only, so the
number is the same string however it was typed back.
"""

SUFFIX_LENGTH: Final[int] = 6
SUFFIX_BITS: Final[int] = SUFFIX_LENGTH * 5
DATE_FORMAT: Final[str] = "%y%m%d"
SEPARATOR: Final[str] = "-"

_ORDER_NUMBER: Final[re.Pattern[str]] = re.compile(
    rf"^\d{{6}}{SEPARATOR}[{CROCKFORD_ALPHABET}]{{{SUFFIX_LENGTH}}}$",
)


@dataclass(frozen=True, kw_only=True)
class OrderNumber(ValueObject):
    """The short number a customer and a manager call an order by.

    Not the identifier of the order — that is ``OrderId``, a UUID nobody can
    read out over the phone. This one is **derived** from the id and the
    moment of placement, in the domain and without asking anybody: the day
    the order was placed, then thirty bits of the id's own randomness spelled
    in an alphabet made for reading aloud. ``240913-3K7QXA`` is a number a
    person can say, a manager can find, and two processes can mint at the
    same instant without a counter between them.

    There is deliberately no database sequence behind it. A sequence is a
    counter to back up, to reset after a restore and to ask the database for
    inside a domain service — an I/O call in the one layer that is supposed
    to have none — and it caps the number at however many digits the check
    allows. Nothing here grows: the suffix has the same width on the first
    order and the millionth. What a sequence would have given and this does
    not is gaplessness, which no one needs, and monotonicity, which the day
    prefix keeps at the granularity people actually use.

    Uniqueness is probabilistic in the way a UUID's is. Thirty bits leave a
    shop placing a hundred orders a day one collision in roughly six hundred
    years, and the unique index on the column is what turns that day into a
    refused insert rather than two orders with one number.

    The day is the UTC day, because that is the clock every timestamp in this
    service keeps; it is a prefix that groups and sorts numbers, not the date
    the customer is shown.

    Decoration is not stored here. Prefixes and padding are how presentation
    chooses to show it, and a domain that knew about them would have to be
    edited to change a caption.
    """

    value: str

    @classmethod
    def derive(cls, *, placed_at: datetime, order_id: UUID) -> Self:
        """Spells the number for an order placed at this moment with this id."""
        day = placed_at.astimezone(UTC).strftime(DATE_FORMAT)
        bits = order_id.int & ((1 << SUFFIX_BITS) - 1)
        suffix = "".join(
            CROCKFORD_ALPHABET[(bits >> shift) & 0b11111]
            for shift in range(SUFFIX_BITS - 5, -1, -5)
        )

        return cls(value=f"{day}{SEPARATOR}{suffix}")

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Order number cannot be empty."
            raise EmptyOrderNumberError(msg)

        if not _ORDER_NUMBER.fullmatch(self.value):
            msg = (
                f"Order number {self.value!r} is not valid "
                f"(expected YYMMDD{SEPARATOR}XXXXXX)."
            )
            raise InvalidOrderNumberFormatError(msg)

    def __str__(self) -> str:
        return self.value
