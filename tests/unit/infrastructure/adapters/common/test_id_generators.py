"""Which version of UUID the two new aggregates get their keys from.

Not a test of ``uuid`` — that it mints a version 7 value is its business. What
is pinned is our choice of 7 over 4, which is invisible in the code once the
import line is read and free to be "simplified" by anybody who has not read the
docstring: both are primary keys of tables that only grow, and version 4
scatters consecutive inserts across the whole B-tree instead of keeping them on
neighbouring index pages.
"""

from uuid import UUID

from goldy.infrastructure.adapters.common.uuid7_cart_id_generator import (
    Uuid7CartIdGenerator,
)
from goldy.infrastructure.adapters.common.uuid7_order_id_generator import (
    Uuid7OrderIdGenerator,
)

UUID_VERSION_WITH_A_TIMESTAMP = 7


def test_a_cart_id_is_time_ordered_rather_than_random() -> None:
    generator = Uuid7CartIdGenerator()

    first, second = generator(), generator()

    assert first.version == UUID_VERSION_WITH_A_TIMESTAMP
    assert first != second
    assert isinstance(first, UUID)


def test_an_order_id_is_time_ordered_rather_than_random() -> None:
    generator = Uuid7OrderIdGenerator()

    first, second = generator(), generator()

    assert first.version == UUID_VERSION_WITH_A_TIMESTAMP
    assert first != second
    assert isinstance(first, UUID)
