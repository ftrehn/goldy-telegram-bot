from typing import Final, override

from goldy.application.commands.carts.set_cart_line_quantity.command import (
    SetCartLineQuantityCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.views.cart import CartSummaryView
from goldy.application.error import CartNotFoundError
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.quantity import Quantity


class SetCartLineQuantityHandler(
    CommandHandler[SetCartLineQuantityCommand, CartSummaryView]
):
    """Writes an absolute quantity onto one line of the caller's cart.

    The catalog is not consulted. A line can only be set if it is already
    there, and it only got there through an addition that did check — asking
    again would cost a query per keystroke to re-answer a question whose answer
    the cart screen already shows.

    The quantity is judged by ``Quantity`` rather than here, so "0" and "50000"
    are refused with the same two errors for every caller, and "0" in
    particular never becomes a line meaning none of this.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        cart_command_gateway: CartCommandGateway,
        cart_summary_view_mapper: CartSummaryViewMapper,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._cart_command_gateway: Final[CartCommandGateway] = cart_command_gateway
        self._cart_summary_view_mapper: Final[CartSummaryViewMapper] = (
            cart_summary_view_mapper
        )

    @override
    async def handle(self, command: SetCartLineQuantityCommand) -> CartSummaryView:
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is None:
            msg = f"User '{user_id}' has no cart."
            raise CartNotFoundError(msg)

        product_id = ProductId(value=command.product_id)
        cart.set_item_quantity(product_id, Quantity(value=command.quantity))

        return self._cart_summary_view_mapper.to_view(cart, product_id)
