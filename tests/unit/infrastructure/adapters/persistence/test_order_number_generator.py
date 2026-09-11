"""What a drawn sequence value becomes on its way to a customer.

The sequence itself belongs to the integration suite; two numbers never
colliding is a property of Postgres and not of us. What is ours is the shape:
the counter starts where it does so that the very first order already has a
number a person can read out over the phone, and the value is handed to the
domain as digits with nothing decorating them.
"""

import pytest
from sqlalchemy.exc import SQLAlchemyError

from goldy.domain.orders.values.order_number import OrderNumber
from goldy.infrastructure.adapters.persistence.postgres_order_number_generator import (
    ORDER_NUMBER_SEQUENCE_NAME,
    ORDER_NUMBER_SEQUENCE_START,
    PostgresOrderNumberGenerator,
    order_number_sequence,
)
from goldy.infrastructure.errors import RepoError
from tests.unit.stubs.persistence import failing_session


def test_the_first_number_the_counter_can_hand_out_is_already_readable() -> None:
    """The reason the sequence starts at a thousand rather than at one.

    ``OrderNumber`` insists on four digits, so a sequence starting at 1 would
    refuse the first three hundred orders outright — and a customer reading
    "order 1" out over the phone would be read back a different order anyway.
    """
    number = OrderNumber(value=str(ORDER_NUMBER_SEQUENCE_START))

    assert number.value == "1000"
    assert str(number) == "1000"


def test_a_number_carries_no_decoration_of_any_kind() -> None:
    """Prefixes and padding are a caption; the domain keeps digits."""
    number = OrderNumber(value=str(ORDER_NUMBER_SEQUENCE_START + 43))

    assert number.value == "1043"


def test_the_counter_is_not_attached_to_the_mapped_schema() -> None:
    """Attached, alembic would offer to create what the migration already did.

    What this adapter needs from the sequence is the name to call ``nextval``
    on, and nothing else.
    """
    assert order_number_sequence.name == ORDER_NUMBER_SEQUENCE_NAME
    assert order_number_sequence.metadata is None


async def test_a_counter_that_cannot_be_read_fails_as_our_own_error() -> None:
    """A handler catches ``AppError``; a raw ``SQLAlchemyError`` would pass it."""
    generator = PostgresOrderNumberGenerator(failing_session())

    with pytest.raises(RepoError) as failure:
        await generator()

    assert "order number" in str(failure.value)
    assert isinstance(failure.value.__cause__, SQLAlchemyError)
