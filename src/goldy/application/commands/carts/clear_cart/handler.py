from typing import Final, override

from goldy.application.commands.carts.clear_cart.command import ClearCartCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.views.cart import CartSummaryView
from goldy.application.error import CartNotFoundError


class ClearCartHandler(CommandHandler[ClearCartCommand, CartSummaryView]):
    """Empties the caller's cart.

    Emptying an already empty cart succeeds, because the aggregate's ``clear``
    is idempotent by design: checkout calls the same method, and an operation
    that has already reached the state asked of it is no reason to fail an
    order that otherwise went through.

    A cart row that was never created is a different matter and still refuses.
    ``CartNotFoundError`` here says "there is nothing of yours to empty", which
    the confirmation screen can only reach with a keyboard older than the cart
    itself; inventing a cart in order to empty it would write a row for no
    reason.
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
    async def handle(self, command: ClearCartCommand) -> CartSummaryView:
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is None:
            msg = f"User '{user_id}' has no cart."
            raise CartNotFoundError(msg)

        cart.clear()

        return self._cart_summary_view_mapper.to_view(cart, None)
