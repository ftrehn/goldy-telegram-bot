import logging
from typing import Final, final

from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.error import CartAlreadyExistsError, CartNotFoundError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.events import CartCreated
from goldy.domain.carts.factories.cart_factory import CartFactory
from goldy.domain.common.events_collection import EventsCollection

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class CartProvider:
    """Loads the caller's cart for command handlers, the way ``UserProvider`` does.

    Two questions, answered here and nowhere else. "Give me the cart, it has to
    exist" is what removing a line or emptying the cart asks, and its answer to
    an absent cart is ``CartNotFoundError`` rather than a cart conjured up to
    be emptied. "Give me the cart, start one if there is none" is what adding
    a product and placing an order ask — the first because it is how carts
    come to exist, the second because it then meets an empty cart and refuses
    with ``EmptyCartError``, which is the real backstop against a double tap.

    Starting a cart is an application decision, not a storage one. The
    gateway inserts what it is handed and reports a clash; which of the two
    simultaneous first additions keeps its cart is settled by the unique index,
    and the loser takes the winner's cart from here without an error and
    without a retry the person would notice.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        cart_command_gateway: CartCommandGateway,
        cart_factory: CartFactory,
        events_collection: EventsCollection,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._cart_command_gateway: Final[CartCommandGateway] = cart_command_gateway
        self._cart_factory: Final[CartFactory] = cart_factory
        self._events_collection: Final[EventsCollection] = events_collection

    async def current(self) -> Cart:
        """The cart of the person running this command, which has to exist.

        Raises:
            CartNotFoundError: they have never put anything in a cart.
        """
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is None:
            msg = f"User '{user_id}' has no cart."
            raise CartNotFoundError(msg)

        return cart

    async def current_or_new(self) -> Cart:
        """The cart of the person running this command, started if they have none.

        The event a fresh cart records is withdrawn when the insert loses the
        race: the cart it announces was never written, and an outbox row about
        it would be a fact about nothing.
        """
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is not None:
            return cart

        cart = self._cart_factory.create(user_id)

        try:
            await self._cart_command_gateway.add(cart)
        except CartAlreadyExistsError:
            logger.info("cart_provider: user %s got a cart concurrently", user_id)
            self._withdraw_creation_of(cart)
            cart = await self._cart_command_gateway.by_user_id(user_id)

            if cart is None:
                msg = f"User '{user_id}' has no cart."
                raise CartNotFoundError(msg) from None

        return cart

    def _withdraw_creation_of(self, cart: Cart) -> None:
        for event in [
            event
            for event in self._events_collection.events
            if isinstance(event, CartCreated) and event.cart_id == cart.id
        ]:
            self._events_collection.remove_event(event)
