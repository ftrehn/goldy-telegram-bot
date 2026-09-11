from typing import final, override
from uuid import uuid7

from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.values.order_id import OrderId


@final
class Uuid7OrderIdGenerator(OrderIdGenerator):
    """Mints order ids as UUIDv7, for the reason user ids are minted that way.

    The id is the primary key of a table that only ever grows, and version 7
    carries a timestamp in its high bits: orders placed one after another land
    on neighbouring index pages instead of scattering an insert across the
    whole B-tree.

    Synchronous, unlike ``OrderNumberGenerator`` beside it. A UUID is made up
    locally and needs nobody's permission; the human-readable number has to be
    unique and increasing, which means asking the database.
    """

    @override
    def __call__(self) -> OrderId:
        return OrderId(uuid7())
