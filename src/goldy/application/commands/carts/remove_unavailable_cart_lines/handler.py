from typing import Final, override

from goldy.application.commands.carts.remove_unavailable_cart_lines.command import (
    RemoveUnavailableCartLinesCommand,
)
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.views.cart import CartSummaryView
from goldy.application.error import CartNotFoundError


class RemoveUnavailableCartLinesHandler(
    CommandHandler[RemoveUnavailableCartLinesCommand, CartSummaryView]
):
    """Removes the lines whose products the catalog no longer holds.

    Availability is asked for the whole cart in one query rather than per line:
    a cart may hold a hundred products, and a hundred round trips inside the
    writing transaction is the kind of loop that is only noticed in production.

    Which lines go is decided by the catalog and never by the aggregate — the
    cart stores nothing but products and quantities, and the whole point of
    that is to have no stale copy of what the catalog says. The handler asks
    with the same predicate the cart screen was drawn with, so the button
    clears exactly the lines it was shown next to.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        cart_command_gateway: CartCommandGateway,
        catalog_query_gateway: CatalogQueryGateway,
        cart_summary_view_mapper: CartSummaryViewMapper,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._cart_command_gateway: Final[CartCommandGateway] = cart_command_gateway
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway
        self._cart_summary_view_mapper: Final[CartSummaryViewMapper] = (
            cart_summary_view_mapper
        )

    @override
    async def handle(
        self,
        command: RemoveUnavailableCartLinesCommand,
    ) -> CartSummaryView:
        user_id = await self._identity_provider.get_current_user_id()
        cart = await self._cart_command_gateway.by_user_id(user_id)

        if cart is None:
            msg = f"User '{user_id}' has no cart."
            raise CartNotFoundError(msg)

        product_ids = [line.product_id for line in cart.lines]

        if product_ids:
            existing = set(
                await self._catalog_query_gateway.read_existing_product_ids(
                    product_ids,
                ),
            )

            for product_id in product_ids:
                if product_id not in existing:
                    cart.remove_item(product_id)

        return self._cart_summary_view_mapper.to_view(cart, None)
