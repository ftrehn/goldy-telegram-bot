from dataclasses import dataclass
from typing import Final, Self, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.common.values.errors import (
    NonPositiveQuantityError,
    QuantityLimitExceededError,
)

MAX_QUANTITY: Final[int] = 10000


@dataclass(frozen=True, kw_only=True)
class Quantity(ValueObject):
    """How many pieces of one product are being bought.

    A whole number rather than a ``Decimal``: the whole assortment is sold by
    the piece, the ``+``/``-`` buttons in the chat move by one, and an integer
    multiplier keeps ``Money.times`` exact — a price with two decimal places
    times a whole number always has two decimal places, so no rounding policy
    is needed and no kopeck can go missing from an order total.

    Zero does not exist by construction. Taking a product out of the cart is
    ``remove_item``, not a quantity of nothing: a line that means "none of
    this" is a line every reader downstream has to remember to skip.

    The ceiling is ten thousand rather than a thousand because a shop with
    price types is a wholesale shop: a thousand pieces of ordinary fastenings
    is reached on the first real order.
    """

    value: int

    @override
    def _validate(self) -> None:
        if self.value < 1:
            msg = f"Quantity must be at least 1, got {self.value}."
            raise NonPositiveQuantityError(msg)

        if self.value > MAX_QUANTITY:
            msg = f"Quantity cannot exceed {MAX_QUANTITY}, got {self.value}."
            raise QuantityLimitExceededError(msg)

    def __add__(self, other: Self) -> Self:
        """Adds two quantities, with the ceiling enforced by validation.

        This is why ``Cart.add_item`` has no limit check of its own: pressing
        ``+`` a thousand times is refused here, once, for every caller.
        """
        return type(self)(value=self.value + other.value)

    def __str__(self) -> str:
        return str(self.value)
