from typing import Final, override

from goldy.application.commands.carts.decrease_cart_line.command import (
    DecreaseCartLineCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.services.cart_provider import CartProvider
from goldy.application.common.views.cart import CartSummaryView
from goldy.domain.catalog.values.product_id import ProductId


class DecreaseCartLineHandler(CommandHandler[DecreaseCartLineCommand, CartSummaryView]):
    """Lowers one line of the caller's cart by a single piece.

    Takes the cart through ``current`` and not ``current_or_new``: there is
    nothing to lower in a cart that does not exist, and conjuring one up would
    turn a stale keyboard into a silent no-op the customer reads as a working
    button. ``CartLineNotFoundError`` from the aggregate travels on for the
    same reason — the cart screen redraws itself from ``GetCartQuery`` after
    every callback, so a refusal is seen and corrected in one tap.
    """

    def __init__(
        self,
        cart_provider: CartProvider,
        cart_summary_view_mapper: CartSummaryViewMapper,
    ) -> None:
        self._cart_provider: Final[CartProvider] = cart_provider
        self._cart_summary_view_mapper: Final[CartSummaryViewMapper] = (
            cart_summary_view_mapper
        )

    @override
    async def handle(self, command: DecreaseCartLineCommand) -> CartSummaryView:
        cart = await self._cart_provider.current()

        product_id = ProductId(value=command.product_id)
        cart.decrease_item(product_id)

        return self._cart_summary_view_mapper.to_view(cart, product_id)
