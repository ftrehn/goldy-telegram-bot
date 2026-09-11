from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import (
    EmptyDeliveryAddressError,
    TooLongDeliveryAddressError,
    TooShortDeliveryAddressError,
)

MIN_DELIVERY_ADDRESS_LENGTH: Final[int] = 10
MAX_DELIVERY_ADDRESS_LENGTH: Final[int] = 500


@dataclass(frozen=True, kw_only=True)
class DeliveryAddress(ValueObject):
    """Where the order is going, as one piece of text.

    Free text rather than a structure of city, street and building, because the
    person who reads it is the courier and they read it as text; in 1C the
    delivery address of an order is contact information in a string too. Four
    fields would cost three extra screens in the chat and buy nothing for
    whoever drives.

    The lower bound is what turns away "home" and "here": an address too short
    to be an address is a delivery that will need a phone call anyway.
    """

    value: str

    @override
    def _validate(self) -> None:
        stripped = self.value.strip()

        if not stripped:
            msg = "Delivery address cannot be empty."
            raise EmptyDeliveryAddressError(msg)

        if len(stripped) < MIN_DELIVERY_ADDRESS_LENGTH:
            msg = (
                f"Delivery address must be at least "
                f"{MIN_DELIVERY_ADDRESS_LENGTH} characters, got {len(stripped)}."
            )
            raise TooShortDeliveryAddressError(msg)

        if len(self.value) > MAX_DELIVERY_ADDRESS_LENGTH:
            msg = (
                f"Delivery address cannot be longer than "
                f"{MAX_DELIVERY_ADDRESS_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongDeliveryAddressError(msg)

    def __str__(self) -> str:
        return self.value
