import logging
from typing import Final, final, override

from sqlalchemy import (
    Sequence as SaSequence,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from goldy.domain.orders.ports.number_generator import OrderNumberGenerator
from goldy.domain.orders.values.order_number import OrderNumber
from goldy.infrastructure.errors import RepoError

logger: Final[logging.Logger] = logging.getLogger(__name__)

ORDER_NUMBER_SEQUENCE_NAME: Final[str] = "orders_number_seq"
ORDER_NUMBER_SEQUENCE_START: Final[int] = 1000

order_number_sequence: Final[SaSequence] = SaSequence(
    ORDER_NUMBER_SEQUENCE_NAME,
    start=ORDER_NUMBER_SEQUENCE_START,
)
"""The counter behind every order number.

Deliberately not attached to the metadata. The migration that creates the
orders table creates this sequence too, and a second definition living in the
mapped schema would make alembic offer to create something that already exists.
What is needed here is only the name to call ``nextval`` on.

It starts at 1000 so the very first number already has the four digits
``OrderNumber`` insists on — a customer reading "order 1" out over the phone
would be read back a different order entirely.
"""


@final
class PostgresOrderNumberGenerator(OrderNumberGenerator):
    """Takes the next order number from a Postgres sequence.

    ``nextval`` is the whole reason this port is asynchronous. It is also the
    reason it is a sequence and not a counter row: a sequence hands out a value
    without waiting for the transaction that asked for it, so two people
    confirming their carts at the same instant get two different numbers
    without either of them queueing behind the other.

    The price is gaps. A transaction that rolls back keeps the number it drew,
    and nothing gives it back — which is correct here, because gapless
    numbering means a row held under a lock, and that means every checkout in
    the shop happening strictly one after another.

    A clash is therefore not a scenario: the sequence never yields one value
    twice, so the unique index on ``orders.number`` guards against a hand-typed
    insert and nothing else. There is no retry here and no error to retry on.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final[AsyncSession] = session

    @override
    async def __call__(self) -> OrderNumber:
        """The next number nobody has been given.

        Raises:
            RepoError: the sequence could not be read.
        """
        try:
            result = await self._session.execute(
                select(order_number_sequence.next_value())
            )
            drawn: int = result.scalar_one()
        except SQLAlchemyError as e:
            logger.exception("failed to draw the next order number")
            msg = "Failed to draw the next order number."
            raise RepoError(msg) from e

        return OrderNumber(value=str(drawn))
