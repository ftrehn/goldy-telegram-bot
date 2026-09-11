import re
from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import (
    EmptyOrderNumberError,
    InvalidOrderNumberFormatError,
)

_ORDER_NUMBER: Final[re.Pattern[str]] = re.compile(r"^\d{4,10}$")


@dataclass(frozen=True, kw_only=True)
class OrderNumber(ValueObject):
    """The short number a customer and a manager call an order by.

    Not the identifier of the order — that is ``OrderId``, a UUID nobody can
    read out over the phone. This one comes from a database sequence, which
    makes two numbers differ at a glance and collide never.

    Decoration is not stored here. Prefixes and padding ("№ 001043") are how
    presentation chooses to show it, and a domain that knew about them would
    have to be edited to change a caption.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Order number cannot be empty."
            raise EmptyOrderNumberError(msg)

        if not _ORDER_NUMBER.fullmatch(self.value):
            msg = f"Order number {self.value!r} is not valid (expected 4 to 10 digits)."
            raise InvalidOrderNumberFormatError(msg)

    def __str__(self) -> str:
        return self.value
