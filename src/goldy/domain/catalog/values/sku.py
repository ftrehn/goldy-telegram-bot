from dataclasses import dataclass
from typing import Final, override

from goldy.domain.catalog.errors import EmptySkuError, TooLongSkuError
from goldy.domain.common.value_object import ValueObject

MAX_SKU_LENGTH: Final[int] = 64


@dataclass(frozen=True, kw_only=True)
class Sku(ValueObject):
    """The code a customer finds a product by, alongside its name.

    Owned by 1C: the bot stores and displays it and never assigns one. It is
    validated here regardless, because an order keeps it as a snapshot and a
    blank article on a placed order is a defect of ours, not of the source.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = "SKU cannot be empty."
            raise EmptySkuError(msg)

        if len(self.value) > MAX_SKU_LENGTH:
            msg = (
                f"SKU cannot be longer than {MAX_SKU_LENGTH} characters, "
                f"got {len(self.value)}."
            )
            raise TooLongSkuError(msg)

    def __str__(self) -> str:
        return self.value
