from typing import Final, override

from goldy.application.commands.carts.remove_cart_line.command import (
    RemoveCartLineCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.services.cart_provider import CartProvider
from goldy.application.common.views.cart import CartSummaryView
from goldy.domain.catalog.values.product_id import ProductId


class RemoveCartLineHandler(CommandHandler[RemoveCartLineCommand, CartSummaryView]):
    """Drops one line from the caller's cart.

    Neither the missing cart nor the missing line is swallowed. Removal is not
    idempotent in this project — the aggregate raises
    ``CartLineNotFoundError`` and a test pins that down — and both refusals
    have their own message on the screen, so the customer is told the line is
    already gone rather than shown a button that appears to have done nothing.
    Reporting success over a failure would also be a lie the transaction
    pipeline commits: it has no other way to learn the work did not happen.
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
    async def handle(self, command: RemoveCartLineCommand) -> CartSummaryView:
        cart = await self._cart_provider.current()

        product_id = ProductId(value=command.product_id)
        cart.remove_item(product_id)

        return self._cart_summary_view_mapper.to_view(cart, product_id)
