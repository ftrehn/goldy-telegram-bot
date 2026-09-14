"""Stand-ins for the generators the domain asks an identifier of.

Deterministic, like ``StubUserIdGenerator``: an assertion about which order was
created only reads if the test already knows what it was going to be called.
"""

from typing import final, override
from uuid import UUID

from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.values.order_id import OrderId


@final
class StubCartIdGenerator(CartIdGenerator):
    def __init__(self, start: int = 1) -> None:
        self._next: int = start

    @override
    def __call__(self) -> CartId:
        cart_id = CartId(UUID(int=self._next))
        self._next += 1
        return cart_id


@final
class StubOrderIdGenerator(OrderIdGenerator):
    def __init__(self, start: int = 1) -> None:
        self._next: int = start

    @override
    def __call__(self) -> OrderId:
        order_id = OrderId(UUID(int=self._next))
        self._next += 1
        return order_id
