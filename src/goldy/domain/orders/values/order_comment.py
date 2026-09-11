from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import EmptyOrderCommentError, TooLongOrderCommentError

MAX_ORDER_COMMENT_LENGTH: Final[int] = 500


@dataclass(frozen=True, kw_only=True)
class OrderComment(ValueObject):
    """What the customer asked for in their own words.

    No comment is modelled as no ``OrderComment`` at all rather than an empty
    one, the way ``MessengerUsername`` is: an empty string and a missing value
    are two spellings of the same thing, and code that has to handle both
    eventually handles only one.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "Order comment cannot be empty."
            raise EmptyOrderCommentError(msg)

        if len(self.value) > MAX_ORDER_COMMENT_LENGTH:
            msg = (
                f"Order comment cannot be longer than "
                f"{MAX_ORDER_COMMENT_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongOrderCommentError(msg)

    def __str__(self) -> str:
        return self.value
