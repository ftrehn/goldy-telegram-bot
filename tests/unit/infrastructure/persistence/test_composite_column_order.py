"""The column order every composite of this wave is rebuilt from.

A composite is rebuilt positionally, so swapping two of its columns swaps the
values with nothing failing — until somebody reads a delivery note and finds a
phone number where a surname belongs. The order is stated three times: in the
table definition, in the ``composite(...)`` call, and in the field order of the
value object itself. Two of those three can be inspected without a database,
and both are checked here against one another.

The third cannot. ``setup_map_tables()`` must run exactly once per process and
the integration suite runs it in its own conftest, so a unit test that mapped
the classes would make ``pytest tests`` fail on an already-mapped class — the
``composite(...)`` arguments are therefore pinned by an integration test that
writes an order and reads it back, and what is guarded here is the pair of
declarations that test would not name if it failed.
"""

from dataclasses import fields
from typing import Final

from sqlalchemy import Table

from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.values.money import Money
from goldy.domain.orders.values.recipient import Recipient
from goldy.infrastructure.persistence.models import order_items_table, orders_table
from goldy.infrastructure.persistence.models.order import PAYMENT_COLUMNS

type CompositeColumns = tuple[tuple[str, str], ...]
"""Pairs of ``(column name, field name)``, in the order the composite takes."""

RECIPIENT_MAPPING: Final[CompositeColumns] = (
    ("recipient_first_name", "first_name"),
    ("recipient_last_name", "last_name"),
    ("recipient_phone", "phone_number"),
)

UNIT_MAPPING: Final[CompositeColumns] = (
    ("unit_id", "source_id"),
    ("unit_name", "name"),
)

MONEY_MAPPING: Final[CompositeColumns] = (
    ("unit_price_amount", "amount"),
    ("unit_price_currency", "currency"),
)


def _columns_in_table_order(table: Table, expected: CompositeColumns) -> list[str]:
    """The named columns, in the order the *table* declares them.

    Selected by membership rather than by index, so the expected order is not
    smuggled back into the answer the assertion is about.
    """
    wanted = {column_name for column_name, _ in expected}
    return [column.name for column in table.columns if column.name in wanted]


def test_the_recipient_columns_sit_in_the_field_order_of_the_value() -> None:
    """Swapped, a delivery note prints a phone number where a surname belongs."""
    columns = _columns_in_table_order(orders_table, RECIPIENT_MAPPING)

    assert columns == [column_name for column_name, _ in RECIPIENT_MAPPING]
    assert [field.name for field in fields(Recipient)] == [
        field_name for _, field_name in RECIPIENT_MAPPING
    ]


def test_the_unit_columns_sit_in_the_field_order_of_the_value() -> None:
    """Swapped, a line would claim to be measured in ``1c-unit-796``."""
    columns = _columns_in_table_order(order_items_table, UNIT_MAPPING)

    assert columns == [column_name for column_name, _ in UNIT_MAPPING]
    assert [field.name for field in fields(UnitOfMeasure)] == [
        field_name for _, field_name in UNIT_MAPPING
    ]


def test_the_price_columns_sit_in_the_field_order_of_money() -> None:
    columns = _columns_in_table_order(order_items_table, MONEY_MAPPING)

    assert columns == [column_name for column_name, _ in MONEY_MAPPING]
    assert [field.name for field in fields(Money)] == [
        field_name for _, field_name in MONEY_MAPPING
    ]


def test_the_columns_left_out_of_the_mapping_are_columns_that_exist() -> None:
    """A misspelled exclusion excludes nothing, and says nothing while doing it.

    ``exclude_properties`` takes names and does not check them, so a typo in
    ``PAYMENT_COLUMNS`` would quietly put a ``payment_confirmed_at`` attribute
    on ``Order`` — domain state nobody maintains, on the aggregate the owner
    decided has no payment in it at all.
    """
    assert set(PAYMENT_COLUMNS) <= set(orders_table.c.keys())
