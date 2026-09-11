from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from goldy.domain.common.values.currency import Currency


@dataclass(frozen=True, slots=True)
class MoneyView:
    """An amount together with the currency it is counted in, flattened.

    Primitives rather than ``Money``, for the reason ``UserView`` carries a
    phone number as text: a view crosses out of the domain, and a price
    formatter that took a ``Money`` would make presentation depend on domain
    internals it has no business knowing.

    Kept as one object rather than spread over ``*_amount`` and ``*_currency``
    pairs because the two never travel apart — every screen that prints an
    amount also prints its currency, and a pair of loose fields is a pair
    somebody eventually renders half of.
    """

    amount: Decimal
    currency: str

    @classmethod
    def zero(cls, currency: Currency = Currency.RUB) -> Self:
        """Nothing at all, which is what an empty cart comes to."""
        return cls(amount=Decimal("0.00"), currency=currency.value)
