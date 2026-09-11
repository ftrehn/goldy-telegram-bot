from typing import Final, override

from goldy.application.commands.carts.repeat_order.command import RepeatOrderCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.services.purchasable_products_service import (
    PurchasableProductsService,
)
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.cart import CartRepeatView
from goldy.application.error import OrderNotFoundError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.services.authorization.permission import (
    IsOrderOwner,
    OrderAccessContext,
)
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.services.access_service import AccessService


class RepeatOrderHandler(CommandHandler[RepeatOrderCommand, CartRepeatView]):
    """Puts back in the cart what this customer bought last time, as sold today.

    Three decisions, in the order they become visible on the screen.

    **Nothing crosses over from the snapshot but the product and the quantity.**
    ADR-0003 keeps a name, an article, a unit and a price on every order line so
    that the document goes on saying what was agreed; reusing any of that here
    would sell at a price that has expired, which the ADR forbids outright. The
    cart holds no prices at all, so the only thing that has to be established is
    whether each product can be bought today — and everything the customer then
    sees is priced afresh when the cart screen renders.

    **The cart is merged into, never emptied.** Repeating into a cart somebody
    has spent ten minutes assembling would destroy work no screen can restore,
    while a merge leaves at worst a few extra lines on the one screen built to
    remove them. Products the order names are *set* to the order's quantity
    rather than increased by it, so a second tap leaves exactly the cart the
    first one produced; products it does not name are left alone. What the
    customer is promised on the confirmation screen is therefore the whole
    truth: "your cart keeps what it holds, and the order's positions arrive at
    the order's quantities".

    **Whatever could not be carried over is named.** A product the import
    dropped, one a sweep deactivated and one this customer's price list no
    longer covers are all skipped and all reported, because a repeat that
    silently produced a shorter cart would be discovered at the till.

    The ceiling on cart lines is deliberately not restated here. ``add_item``
    refuses the hundred-and-first product, the refusal reaches the person as
    "the cart is full" through the error table, and ``TransactionPipeline``
    rolls the half-finished merge back — so a repeat that does not fit leaves
    the cart exactly as it was rather than half repeated.
    """

    def __init__(
        self,
        user_provider: UserProvider,
        access_service: AccessService,
        order_command_gateway: OrderCommandGateway,
        cart_command_gateway: CartCommandGateway,
        purchasable_products: PurchasableProductsService,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._access_service: Final[AccessService] = access_service
        self._order_command_gateway: Final[OrderCommandGateway] = order_command_gateway
        self._cart_command_gateway: Final[CartCommandGateway] = cart_command_gateway
        self._purchasable_products: Final[PurchasableProductsService] = (
            purchasable_products
        )

    @override
    async def handle(self, command: RepeatOrderCommand) -> CartRepeatView:
        """Reads the order, checks who is asking, then fills the cart.

        The order is loaded through the command gateway rather than the read
        model even though nothing about it is written. The card query answers
        anyone the order belongs to *or* any member of staff, and a manager
        pouring a customer's order into their own cart is not a feature — the
        aggregate carries ``customer_id`` for ``IsOrderOwner`` to refuse on, and
        the lines carry the quantities this has to copy anyway.

        Authorisation comes before the catalog is read and before the cart is
        created, so a guessed identifier costs a stranger nothing at all: no
        query against their price list, and no cart row written for whoever was
        guessing.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the order belongs to somebody else.
            PriceTypeNotConfiguredError: no price list resolves for this person.
            UnsupportedPriceTypeError: their price list is in a currency this
                shop cannot price in.
            CartLineLimitExceededError: the merged cart would hold more than
                ``MAX_CART_LINES`` different products.
        """
        customer = await self._user_provider.current()
        order_id = OrderId(command.order_id)
        order = await self._order_command_gateway.by_id(order_id)

        if order is None:
            msg = f"Order '{order_id}' does not exist."
            raise OrderNotFoundError(msg)

        self._access_service.authorize(
            IsOrderOwner(),
            context=OrderAccessContext(
                subject=customer,
                order_customer_id=order.customer_id,
            ),
        )

        purchasable = await self._purchasable_products.among(
            [line.product_id for line in order.lines],
        )
        cart = await self._cart_command_gateway.ensure_for(customer.id)

        return self._merge(order, cart, purchasable)

    def _merge(
        self,
        order: Order,
        cart: Cart,
        purchasable: frozenset[ProductId],
    ) -> CartRepeatView:
        """Walks the order in its own order and reports what happened to it.

        By position rather than by whatever the catalog answered in, so that a
        partially repeated order is skipped and filled the way the customer
        reads it — and so an order too big for the cart fills it from the top
        instead of from wherever the query happened to start.

        The names of the skipped products are taken off the order line, which
        for a product the import dropped is the last place on earth that still
        holds one.
        """
        moved = 0
        skipped: list[str] = []

        for line in order.lines:
            if line.product_id not in purchasable:
                skipped.append(line.name.value)
                continue

            self._put(cart, line)
            moved += 1

        return CartRepeatView(
            moved_line_count=moved,
            skipped_product_names=tuple(skipped),
            line_count=cart.line_count,
        )

    def _put(self, cart: Cart, line: OrderLine) -> None:
        """Gives the cart this line's quantity, whatever it held before.

        Two aggregate calls because the cart deliberately offers no upsert:
        ``add_item`` accumulates, which is right under a ``+`` button and wrong
        under this one, and ``set_item_quantity`` needs a line to already exist.
        Choosing between them is a decision about what "repeat" means rather
        than a second statement of a rule the aggregate holds — both refusals
        the cart can make still come from the cart.
        """
        if cart.line_for(line.product_id) is None:
            cart.add_item(line.product_id, line.quantity)
            return

        cart.set_item_quantity(line.product_id, line.quantity)
