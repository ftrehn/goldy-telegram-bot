from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.orders.values.order_number import OrderNumber


class OrderNumberGenerator(Protocol):
    """Hands out the next human-readable order number.

    **Asynchronous on purpose**, unlike every other generator in this project.
    An order number has to be unique and increasing, which means asking a
    database sequence for it, which means I/O. The id generators stay
    synchronous because a UUID needs nobody's permission.

    This is stated here so the difference is not mistaken for an oversight and
    quietly "fixed" back — making it synchronous would push the number out of
    the domain and split placing an order across two layers.
    """

    @abstractmethod
    async def __call__(self) -> OrderNumber:
        raise NotImplementedError
