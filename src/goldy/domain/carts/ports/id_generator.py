from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.domain.carts.values.cart_id import CartId


class CartIdGenerator(Protocol):
    @abstractmethod
    def __call__(self) -> CartId:
        raise NotImplementedError
