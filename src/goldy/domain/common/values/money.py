from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Self, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.errors import (
    CurrencyMismatchError,
    MoneyAmountOutOfRangeError,
    NegativeMoneyAmountError,
    TooPreciseMoneyAmountError,
)
from goldy.domain.common.values.quantity import Quantity

MONEY_SCALE: Final[int] = 2
MAX_MONEY_AMOUNT: Final[Decimal] = Decimal("9999999999.99")


@dataclass(frozen=True)
class Money(ValueObject):
    """An amount of money together with the currency it is counted in.

    A bare ``Decimal`` would let two prices in different currencies be added
    silently, which is the one arithmetic mistake nobody notices until the
    invoice; ``float`` is not a candidate at all.

    Not ``kw_only`` unlike most value objects here, because this one is mapped
    as a SQLAlchemy ``composite`` over two columns and SQLAlchemy rebuilds it
    positionally when loading a row. Field order is part of the mapping, the
    same way it is for ``FullName``.
    """

    amount: Decimal
    currency: Currency = Currency.RUB

    @classmethod
    def zero(cls, currency: Currency = Currency.RUB) -> Self:
        return cls(Decimal("0.00"), currency)

    def times(self, quantity: Quantity) -> Self:
        """Multiplies a unit price by a whole number of pieces.

        Named rather than spelled ``__mul__`` on purpose: multiplying money by
        a count is not arithmetic between two numbers, and an operator would
        make ``price * price`` look like something that means anything.
        """
        return type(self)(self.amount * quantity.value, self.currency)

    def __add__(self, other: Self) -> Self:
        """Adds two amounts of the same currency.

        Raises:
            CurrencyMismatchError: the two amounts are in different currencies.
        """
        if other.currency is not self.currency:
            msg = (
                f"Cannot add {other.currency.value} to {self.currency.value} — "
                f"amounts in different currencies are not comparable."
            )
            raise CurrencyMismatchError(msg)

        return type(self)(self.amount + other.amount, self.currency)

    @override
    def _validate(self) -> None:
        if not self.amount.is_finite():
            msg = f"Money amount must be a finite number, got {self.amount}."
            raise MoneyAmountOutOfRangeError(msg)

        if self.amount < 0:
            msg = f"Money amount cannot be negative, got {self.amount}."
            raise NegativeMoneyAmountError(msg)

        if self.amount > MAX_MONEY_AMOUNT:
            msg = f"Money amount cannot exceed {MAX_MONEY_AMOUNT}, got {self.amount}."
            raise MoneyAmountOutOfRangeError(msg)

        exponent = self.amount.as_tuple().exponent
        scale = -exponent if isinstance(exponent, int) else 0

        if scale > MONEY_SCALE:
            msg = (
                f"Money amount cannot have more than {MONEY_SCALE} decimal "
                f"places, got {self.amount}."
            )
            raise TooPreciseMoneyAmountError(msg)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency.value.upper()}"
