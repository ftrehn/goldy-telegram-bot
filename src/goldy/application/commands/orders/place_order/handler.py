from typing import Final, override

from goldy.application.commands.orders.place_order.command import PlaceOrderCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.services.cart_pricing_service import (
    CartPricing,
    CartPricingService,
)
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.order import OrderPlacedView
from goldy.application.error import CartRepricedError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.orders.checkout import Checkout
from goldy.domain.orders.services.checkout_service import CheckoutService
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.recipient import Recipient
from goldy.domain.users.values.phone_number import PhoneNumber


class PlaceOrderHandler(CommandHandler[PlaceOrderCommand, OrderPlacedView]):
    """Places the order and empties the cart, both or neither.

    Five collaborators, which is the ceiling ``PLR0913`` allows and the reason
    ``CartPricingService`` exists at all: resolving a price type and reading
    prices would otherwise be two more.

    Emptying the cart is not done here — ``CheckoutService`` does it, inside the
    same transaction as the insert. That is what makes a second confirmation
    tap meet ``EmptyCartError`` instead of placing the same order twice, and it
    is the only one of the three defences against a double tap that works
    across platforms. A failure between the two halves would otherwise leave
    somebody holding an order and a full cart, ready to place it again.

    Stock is not consulted anywhere in here. What the bot holds is a stale
    projection of 1C with no reservation behind it, so refusing on it would
    turn away orders the shop could fill while still not preventing
    overselling; a manager checks the real stock, which is what ``CONFIRMED``
    means.
    """

    def __init__(
        self,
        user_provider: UserProvider,
        cart_command_gateway: CartCommandGateway,
        cart_pricing_service: CartPricingService,
        checkout_service: CheckoutService,
        order_command_gateway: OrderCommandGateway,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._cart_command_gateway: Final[CartCommandGateway] = cart_command_gateway
        self._cart_pricing_service: Final[CartPricingService] = cart_pricing_service
        self._checkout_service: Final[CheckoutService] = checkout_service
        self._order_command_gateway: Final[OrderCommandGateway] = order_command_gateway

    @override
    async def handle(self, command: PlaceOrderCommand) -> OrderPlacedView:
        """Prices the cart, checks it against the screen, places the order.

        The cart is checked for being empty before the totals are compared, and
        the order of those two matters more than it looks. A second tap on
        "confirm" arrives with the totals of a cart that no longer exists, so
        comparing first would refuse it as a repricing — while the dialog is
        written to catch ``EmptyCartError`` and say "the order is already
        placed", which is what actually happened.

        Raises:
            EmptyCartError: there is nothing in the cart to order.
            CartRepricedError: the cart is no longer worth what the
                confirmation screen said it was.
            UnpricedCartLineError: the catalog lost one of the products between
                the screen and the command.
        """
        customer = await self._user_provider.current()
        cart = await self._cart_command_gateway.ensure_for(customer.id)
        cart.ensure_not_empty()

        pricing = await self._cart_pricing_service.for_cart(cart)
        self._ensure_not_repriced(command, cart, pricing)

        order = await self._checkout_service.checkout(
            self._build_checkout(command, cart, pricing),
        )
        await self._order_command_gateway.add(order)

        return OrderPlacedView(order_id=order.id, order_number=str(order.number))

    def _ensure_not_repriced(
        self,
        command: PlaceOrderCommand,
        cart: Cart,
        pricing: CartPricing,
    ) -> None:
        """Refuses to charge more — or less — than the screen promised.

        Both directions are refused, because a total that dropped means the
        cart is not the one the customer looked at either.

        A cart that cannot be priced at all is let through to
        ``CheckoutService``, which refuses it naming the line it happened on.

        Raises:
            CartRepricedError: the line count or the total moved.
        """
        if cart.line_count != command.expected_line_count:
            msg = (
                f"Cart holds {cart.line_count} line(s), the confirmation "
                f"screen showed {command.expected_line_count}."
            )
            raise CartRepricedError(msg)

        total = pricing.total_for(cart)

        if total is not None and total.amount != command.expected_total:
            msg = (
                f"Cart is now worth {total.amount}, the confirmation screen "
                f"showed {command.expected_total}."
            )
            raise CartRepricedError(msg)

    def _build_checkout(
        self,
        command: PlaceOrderCommand,
        cart: Cart,
        pricing: CartPricing,
    ) -> Checkout:
        """Turns what somebody typed into the values the domain accepts.

        The phone number goes through ``from_raw`` rather than the constructor:
        "8 916 123-45-67" is how a number is typed by hand, and the constructor
        would refuse a perfectly ordinary entry.

        Raises:
            DomainFieldError: the address, the name, the phone number or the
                comment is not something an order can carry.
        """
        return Checkout(
            cart=cart,
            priced_products=pricing.priced_products,
            delivery_address=DeliveryAddress(value=command.delivery_address),
            recipient=Recipient(
                command.recipient_first_name,
                command.recipient_last_name,
                PhoneNumber.from_raw(command.recipient_phone_number),
            ),
            comment=(
                None if command.comment is None else OrderComment(value=command.comment)
            ),
            price_type_id=pricing.price_type_id,
        )
