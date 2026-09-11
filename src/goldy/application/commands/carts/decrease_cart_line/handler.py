from typing import Final, override

from goldy.application.commands.carts.decrease_cart_line.command import (
    DecreaseCartLineCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.views.cart import CartSummaryView
from goldy.application.error import CartNotFoundError
from goldy.domain.catalog.values.product_id import ProductId


class DecreaseCartLineHandler(CommandHandler[DecreaseCartLineCommand, CartSummaryView]):
    """Lowers one line of the caller's cart by a single piece.

    Reads the cart through ``by_user_id`` and not ``ensure_for``: there is
    nothing to lower in a cart that does not exist, and conjuring one up would
    turn a stale keyboard into a silent no-op the customer reads as a working
    button. ``CartLineNotFoundError`` from the aggregate travels on for the
    same reason — the cart screen redraws itself from ``GetCartQuery`` after
    every callback, so a refusal is seen and corrected in one tap.
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
    async def handle(self, command: DecreaseCartLineCommand) -> CartSummaryView:
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is None:
            msg = f"User '{user_id}' has no cart."
            raise CartNotFoundError(msg)

        product_id = ProductId(value=command.product_id)
        cart.decrease_item(product_id)

        return self._cart_summary_view_mapper.to_view(cart, product_id)
