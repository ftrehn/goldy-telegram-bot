from goldy.domain.common.error import DomainError, DomainFieldError


class NegativeMoneyAmountError(DomainFieldError): ...


class TooPreciseMoneyAmountError(DomainFieldError): ...


class MoneyAmountOutOfRangeError(DomainFieldError): ...


class NonPositiveQuantityError(DomainFieldError): ...


class QuantityLimitExceededError(DomainFieldError): ...


class CurrencyMismatchError(DomainError):
    """Two amounts in different currencies were combined.

    Not a field error: each currency is perfectly valid on its own, it is the
    operation over the pair that has no meaning.
    """
