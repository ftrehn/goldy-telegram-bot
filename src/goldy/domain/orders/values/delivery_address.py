import re
from dataclasses import dataclass
from typing import Final, override

from goldy.domain.common.value_object import ValueObject
from goldy.domain.orders.errors import (
    EmptyDeliveryAddressError,
    ForeignDeliveryAddressError,
    IncompleteDeliveryAddressError,
    TooLongDeliveryAddressError,
    TooShortDeliveryAddressError,
)

MIN_DELIVERY_ADDRESS_LENGTH: Final[int] = 10
MAX_DELIVERY_ADDRESS_LENGTH: Final[int] = 500

_CYRILLIC_LETTER: Final[re.Pattern[str]] = re.compile(r"[Ѐ-ӿ]")
_DIGIT: Final[re.Pattern[str]] = re.compile(r"\d")


@dataclass(frozen=True, kw_only=True)
class DeliveryAddress(ValueObject):
    """Where the order is going, as one piece of text.

    Free text rather than a structure of city, street and building, because the
    person who reads it is the courier and they read it as text; in 1C the
    delivery address of an order is contact information in a string too. Four
    fields would cost three extra screens in the chat and buy nothing for
    whoever drives.

    The shop delivers within Russia and nowhere else, and that rule is held
    here as far as text allows without I/O. An address a Russian courier can
    read is written in Cyrillic and names a building, so the value has to
    carry at least one Cyrillic letter and at least one digit: "New York,
    5th Avenue 1" is turned away, and so is "home" and "here". What this does
    not do is check that the town exists — that would take a reference of
    settlements and a fuzzy match against however the person spelled it, and
    a wrong town is still a delivery that gets a phone call, which is where it
    is caught today.

    The lower bound is what turns away an address too short to be one at all.
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

        if _CYRILLIC_LETTER.search(stripped) is None:
            msg = (
                "Delivery address must be written in Cyrillic — "
                "delivery is within Russia."
            )
            raise ForeignDeliveryAddressError(msg)

        if _DIGIT.search(stripped) is None:
            msg = "Delivery address must name a building — it contains no number."
            raise IncompleteDeliveryAddressError(msg)

    def __str__(self) -> str:
        return self.value
