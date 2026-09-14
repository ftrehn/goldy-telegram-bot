from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.orders.entities.order import Order
    from goldy.domain.orders.values.order_id import OrderId


class OrderCommandGateway(Protocol):
    """Write-side access to the :class:`Order` aggregate.

    Whole aggregates, lines included. Every rule this side enforces is about
    the order as a whole — a status transition, who may cancel it, whether the
    address is still editable — and :attr:`Order.total` is derived from the
    lines each time it is asked for, so an order loaded without them would
    report a total of nothing.

    No lookup by number. The number is what a person calls an order in
    conversation, not what the code addresses it by, and every command that
    reaches here has come from a screen that already knows the id.
    """

    @abstractmethod
    async def add(self, order: Order) -> None:
        raise NotImplementedError

    @abstractmethod
    async def by_id(self, order_id: OrderId) -> Order | None:
        raise NotImplementedError
