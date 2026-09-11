from dataclasses import dataclass
from typing import Final, override

from goldy.domain.catalog.errors import (
    EmptySourceIdError,
    EmptyUnitOfMeasureError,
    TooLongSourceIdError,
    TooLongUnitOfMeasureError,
)
from goldy.domain.catalog.values.source_id import MAX_SOURCE_ID_LENGTH
from goldy.domain.common.value_object import ValueObject

MAX_UNIT_OF_MEASURE_NAME_LENGTH: Final[int] = 32


@dataclass(frozen=True)
class UnitOfMeasure(ValueObject):
    """The unit a product is sold in — a piece, a metre, a pack.

    Part of the order line snapshot alongside the name: "2" without "шт" or "м"
    tells the customer nothing, and reading the unit out of the catalog when
    the order is displayed would restore exactly the reference the snapshot
    exists to avoid.

    Two fields rather than one because a future export needs the reference
    while the customer needs the label, which is the same argument ADR-0003
    makes for keeping ``product_id`` on the line. ``source_id`` is a plain
    string and not a ``SourceId`` because this value is mapped as a SQLAlchemy
    ``composite`` and a composite nested inside a composite maps badly — the
    same reason ``Recipient`` holds flat fields. Both rules ``SourceId``
    applies are therefore restated here against the raw string rather than
    inherited: an absent reference is ``None``, while ``""`` is refused like
    everywhere else. A missing attribute arrives from a JSON fixture or an
    exchange message as an empty string far more often than as ``null``, and
    such a value is not NULL in the column and points at nothing in 1C.

    Not ``kw_only`` for that same mapping: SQLAlchemy rebuilds a composite
    positionally, so field order is part of the contract.

    Pack ratio is deliberately absent. Price and quantity are always counted in
    the unit the product is sold in, and the ratio is something a product card
    shows — it lives in the projection.
    """

    source_id: str | None
    name: str

    @override
    def _validate(self) -> None:
        if not self.name.strip():
            msg = "Unit of measure name cannot be empty."
            raise EmptyUnitOfMeasureError(msg)

        if len(self.name) > MAX_UNIT_OF_MEASURE_NAME_LENGTH:
            msg = (
                f"Unit of measure name cannot be longer than "
                f"{MAX_UNIT_OF_MEASURE_NAME_LENGTH} characters, got {len(self.name)}."
            )
            raise TooLongUnitOfMeasureError(msg)

        if self.source_id is None:
            return

        if not self.source_id.strip():
            msg = "Unit of measure source id cannot be empty."
            raise EmptySourceIdError(msg)

        if len(self.source_id) > MAX_SOURCE_ID_LENGTH:
            msg = (
                f"Unit of measure source id cannot be longer than "
                f"{MAX_SOURCE_ID_LENGTH} characters, got {len(self.source_id)}."
            )
            raise TooLongSourceIdError(msg)

    def __str__(self) -> str:
        return self.name
