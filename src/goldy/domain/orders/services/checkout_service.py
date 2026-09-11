import logging
from typing import TYPE_CHECKING, Final, final

from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.common.service import BaseDomainService
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.errors import UnpricedCartLineError
from goldy.domain.orders.placement import Placement
from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.ports.number_generator import OrderNumberGenerator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from goldy.domain.carts.entities.cart_line import CartLine
    from goldy.domain.catalog.values.product_id import ProductId
    from goldy.domain.orders.checkout import Checkout

logger: Final[logging.Logger] = logging.getLogger(__name__)


@final
class CheckoutService(BaseDomainService):
    """Turns a cart into an order, in one operation.

    A domain service because the aggregate is missing two different things at
    once: the generators that mint an id and a number, and the second aggregate
    the operation ends on. Emptying the cart belongs here rather than in a
    handler — "the cart became an order" is a single business operation, and the
    half of it left behind in a handler one day hands the customer an order with
    the same cart still sitting on top of it.

    ``checkout`` is asynchronous, which no other domain service in this project
    is. ``OrderNumberGenerator`` has to ask a database sequence for the next
    number, and that is I/O. The alternative is moving the number out of the
    domain, which splits placing an order across two layers.

    Stock is not consulted. What the bot holds is a stale projection of 1C with
    no reservation behind it, so refusing an order on it would turn away orders
    the shop could actually fill while still not preventing overselling under
    concurrency. A manager checks the real stock — that is what ``CONFIRMED``
    is for.
    """

    def __init__(
        self,
        events_collection: EventsCollection,
        order_id_generator: OrderIdGenerator,
        order_number_generator: OrderNumberGenerator,
    ) -> None:
        self._events_collection: Final[EventsCollection] = events_collection
        self._order_id_generator: Final[OrderIdGenerator] = order_id_generator
        self._order_number_generator: Final[OrderNumberGenerator] = order_number_generator

    async def checkout(self, checkout: Checkout) -> Order:
        """Prices the cart into snapshot lines, places the order, empties the cart.

        Every line is built before anything is minted or emptied, so a cart the
        catalog can no longer price leaves nothing half-done behind — the
        transaction pipeline would otherwise commit exactly that.

        Raises:
            EmptyCartError: there is nothing in the cart to order.
            UnpricedCartLineError: the catalog no longer prices one of the
                products in the cart.
            CurrencyMismatchError: the lines are priced in more than one
                currency.
        """
        cart = checkout.cart
        cart.ensure_not_empty()

        prices: Mapping[ProductId, PricedProduct] = {
            priced.product_id: priced for priced in checkout.priced_products
        }
        lines = tuple(
            self._build_line(position, cart_line, prices)
            for position, cart_line in enumerate(cart.lines, start=1)
        )

        order = Order.place(
            order_id=self._order_id_generator(),
            order_number=await self._order_number_generator(),
            events_collection=self._events_collection,
            placement=Placement(
                customer_id=cart.user_id,
                lines=lines,
                delivery_address=checkout.delivery_address,
                recipient=checkout.recipient,
                comment=checkout.comment,
                price_type_id=checkout.price_type_id,
            ),
        )
        cart.clear()
        logger.debug(
            "checkout_service: cart %s became order %s with %d lines",
            cart.id,
            order.number,
            len(lines),
        )
        return order

    def _build_line(
        self,
        position: int,
        cart_line: CartLine,
        prices: Mapping[ProductId, PricedProduct],
    ) -> OrderLine:
        """Copies one cart line into a snapshot, priced from the catalog.

        Raises:
            UnpricedCartLineError: the catalog lost the product between the
                moment it was shown and the moment it was ordered.
        """
        priced = prices.get(cart_line.product_id)

        if priced is None:
            msg = f"Product '{cart_line.product_id}' has no price and cannot be ordered."
            raise UnpricedCartLineError(msg)

        return OrderLine(
            position=position,
            product_id=priced.product_id,
            sku=priced.sku,
            name=priced.name,
            unit=priced.unit,
            unit_price=priced.unit_price,
            quantity=cart_line.quantity,
        )
