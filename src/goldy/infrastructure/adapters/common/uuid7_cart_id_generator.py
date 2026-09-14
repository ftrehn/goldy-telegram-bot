from typing import final, override
from uuid import uuid7

from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.carts.values.cart_id import CartId


@final
class Uuid7CartIdGenerator(CartIdGenerator):
    """Mints cart ids as UUIDv7.

    Version 7 for the reason ``Uuid7UserIdGenerator`` gives: the value is a
    primary key, and the timestamp in its high bits keeps consecutive inserts
    on neighbouring index pages instead of scattering them across the whole
    B-tree.

    Carts are minted far more often than users — one per person, but created
    lazily on a first addition that may come at any time — which is exactly the
    write pattern a random key spreads worst.
    """

    @override
    def __call__(self) -> CartId:
        return CartId(uuid7())
