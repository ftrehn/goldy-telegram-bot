from dataclasses import dataclass
from typing import Final, override

from goldy.domain.catalog.errors import EmptyProductNameError, TooLongProductNameError
from goldy.domain.common.value_object import ValueObject

MAX_PRODUCT_NAME_LENGTH: Final[int] = 255


@dataclass(frozen=True, kw_only=True)
class ProductName(ValueObject):
    """What the product is called in the catalog.

    Comes from 1C and is copied into an order line as a snapshot, so it is the
    text the customer will still be shown months later when the catalog has
    moved on.
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

    def __str__(self) -> str:
        return self.value
