from dataclasses import dataclass
from typing import Final, override

from goldy.domain.catalog.errors import EmptySourceIdError, TooLongSourceIdError
from goldy.domain.common.value_object import ValueObject

MAX_SOURCE_ID_LENGTH: Final[int] = 128


@dataclass(frozen=True, kw_only=True, order=True)
class SourceId(ValueObject):
    """The id 1C knows one of its own objects by. We never mint one.

    Text rather than a ``UUID`` because 1C exchanges carry composite keys —
    ``guid#guid`` once product variants are switched on — and a ``uuid`` column
    would break the import on the day that happens rather than on the day it
    was designed. See ADR-0002.

    The ceiling is 128 and not 64 for the same reason: a GUID spelled out takes
    36 characters and a composite key 73, so 64 would run out on exactly the
    case the string was chosen for. Widening it afterwards means an ``ALTER``
    over six projection tables and over ``order_items``, which is a migration
    across historical orders.

    The base exists so the length rule is written once. Subclasses add nothing
    but their own name, which is enough: the ``__eq__`` a dataclass generates
    demands both sides be the same class, so a ``ProductId`` never compares
    equal to a ``CategoryId`` holding the same string.

    ``order=True`` is not decoration and must not be dropped. ``ProductId`` is
    half the primary key of ``cart_items``, and SQLAlchemy sorts states by their
    primary key before flushing a delete of more than one row of the same
    mapper — so without ``<`` on this class, emptying a cart holding two
    different products raises ``InvalidRequestError`` deep inside the unit of
    work. That is the ordinary end of every checkout: ``CheckoutService`` clears
    the cart in the same transaction as the insert, so an order of two products
    could not be placed at all. Ordering identifiers by their text is meaningless
    business-wise and harmless, which is why the requirement is met here rather
    than by giving ``cart_items`` a surrogate key it has no other use for.
    """

    value: str

    @override
    def _validate(self) -> None:
        if not self.value.strip():
            msg = f"{type(self).__name__} cannot be empty."
            raise EmptySourceIdError(msg)

        if len(self.value) > MAX_SOURCE_ID_LENGTH:
            msg = (
                f"{type(self).__name__} cannot be longer than "
                f"{MAX_SOURCE_ID_LENGTH} characters, got {len(self.value)}."
            )
            raise TooLongSourceIdError(msg)

    def __str__(self) -> str:
        return self.value
