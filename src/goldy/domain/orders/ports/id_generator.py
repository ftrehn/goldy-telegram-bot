from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.orders.values.order_id import OrderId


class OrderIdGenerator(Protocol):
    @abstractmethod
    def __call__(self) -> OrderId:
        raise NotImplementedError
