from goldy.domain.common.error import DomainError


class CartLineNotFoundError(DomainError): ...


class CartLineLimitExceededError(DomainError): ...


class EmptyCartError(DomainError): ...
