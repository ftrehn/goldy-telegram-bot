from dataclasses import dataclass
from typing import Final, override
from unicodedata import category

from goldy.domain.catalog.errors import (
    EmptySkuError,
    MalformedSkuError,
    TooLongSkuError,
)
from goldy.domain.common.value_object import ValueObject

MAX_SKU_LENGTH: Final[int] = 64
CONTROL_CHARACTER: Final[str] = "Cc"
"""The Unicode category of tabs, line feeds and the like — never part of an article."""


@dataclass(frozen=True, kw_only=True)
class Sku(ValueObject):
    """The code a customer finds a product by, alongside its name.

    Owned by 1C: the bot stores and displays it and never assigns one. It is
    validated here regardless, because an order keeps it as a snapshot and a
    blank article on a placed order is a defect of ours, not of the source.

    **Mandatory for every product.** The article is optional in 1C, but every
    element of its nomenclature has a code, and the exchange contract sends
    the code where the article is blank — so a product without a value here
    is a broken export, not a product. That is what lets an order line keep a
    ``Sku`` rather than a maybe, and a customer always has something to read
    out to a manager.

    Always text, never a number, even when the source stores digits: an
    article is an identifier, not a quantity, and ``"00123"`` and ``"123"``
    name different products. A marketplace or a supplier that keeps articles
    as integers hands them over as their decimal spelling.

    The length is the one bound this class takes from the storage column, and
    it is generous rather than tight: articles differ between 1C, Ozon and a
    supplier's own catalogue, and the domain has no business guessing which of
    them is being imported. Control characters are refused because they are
    never part of an article and always a sign of a broken export.
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

        if any(category(character) == CONTROL_CHARACTER for character in self.value):
            msg = f"SKU {self.value!r} contains control characters."
            raise MalformedSkuError(msg)

    def __str__(self) -> str:
        return self.value
