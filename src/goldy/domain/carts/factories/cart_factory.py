from typing import TYPE_CHECKING, Final, final

from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.ports.id_generator import CartIdGenerator
from goldy.domain.common.events_collection import EventsCollection

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId


@final
class CartFactory:
    """Domain factory for the :class:`Cart` aggregate.

    Exists for the single reason ``UserFactory`` does: a new cart needs an
    identifier and the aggregate has nowhere to get one.

    "Take the person's cart or start a new one" is deliberately not here. That
    decision needs a trip to the gateway, so it belongs to an application
    handler; a factory that reads storage stops being a domain object.
    """

    def __init__(
        self,
        events_collection: EventsCollection,
        cart_id_generator: CartIdGenerator,
    ) -> None:
        self._events_collection: Final[EventsCollection] = events_collection
        self._cart_id_generator: Final[CartIdGenerator] = cart_id_generator

    def create(self, user_id: UserId) -> Cart:
        return Cart.create(
            cart_id=self._cart_id_generator(),
            events_collection=self._events_collection,
            user_id=user_id,
        )
