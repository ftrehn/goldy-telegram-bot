"""Stand-ins for the generators the domain asks an identifier or a number of.

Deterministic, like ``StubUserIdGenerator``: an assertion about which order was
created only reads if the test already knows what it was going to be called.
"""

from typing import final, override
from uuid import UUID

from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.ports.number_generator import OrderNumberGenerator
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_number import OrderNumber

FIRST_ORDER_NUMBER: int = 1001


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


@final
class StubOrderNumberGenerator(OrderNumberGenerator):
    """Hands out consecutive numbers, the way the database sequence will.

    Counts the calls it got, so a test can show that a checkout which failed
    before it had priced everything never reached for a number at all.
    """

    def __init__(self, start: int = FIRST_ORDER_NUMBER) -> None:
        self._next: int = start
        self.calls: int = 0

    @override
    async def __call__(self) -> OrderNumber:
        self.calls += 1
        number = OrderNumber(value=str(self._next))
        self._next += 1
        return number
