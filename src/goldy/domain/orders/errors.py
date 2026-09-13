from goldy.domain.common.error import DomainError, DomainFieldError


class EmptyOrderNumberError(DomainFieldError): ...


class InvalidOrderNumberFormatError(DomainFieldError): ...


class EmptyDeliveryAddressError(DomainFieldError): ...


class TooShortDeliveryAddressError(DomainFieldError): ...


class TooLongDeliveryAddressError(DomainFieldError): ...


class ForeignDeliveryAddressError(DomainFieldError):
    """The address is not written in Cyrillic, so it is not an address in Russia."""


class IncompleteDeliveryAddressError(DomainFieldError):
    """The address names no building — there is not a single digit in it."""


class EmptyOrderCommentError(DomainFieldError): ...


class TooLongOrderCommentError(DomainFieldError): ...


class EmptyCancellationReasonError(DomainFieldError): ...


class TooLongCancellationReasonError(DomainFieldError): ...


class OrderStatusTransitionError(DomainError): ...


class EmptyOrderError(DomainError): ...


class OrderNotEditableError(DomainError): ...


class CustomerCannotCancelProcessedOrderError(DomainError): ...


class CancellationReasonRequiredError(DomainError): ...


class UnpricedCartLineError(DomainError): ...
