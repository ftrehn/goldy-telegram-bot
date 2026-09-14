from typing import Final, override

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.ports.mappers import CartSummaryViewMapper
from goldy.application.common.services.cart_provider import CartProvider
from goldy.application.common.views.cart import CartSummaryView
from goldy.application.error import ProductNotFoundError
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.quantity import Quantity


class AddToCartHandler(CommandHandler[AddToCartCommand, CartSummaryView]):
    """Adds a product to the caller's cart, creating the cart if there is none.

    The catalog is asked whether the product is still there, and asked without
    a price type: the cart stores no prices, so resolving the customer's price
    list here would be work for an answer nothing reads. A product that has
    been withdrawn between the screen being drawn and the button being pressed
    is refused outright, which is the only moment a vanished product can be
    caught before it becomes a cart line nobody can order.

    Whether the person has a cart yet is ``CartProvider``'s question, not
    this handler's: it starts one on the first addition and, when two first
    additions race, hands the loser the cart that won.
    """

    def __init__(
        self,
        cart_provider: CartProvider,
        catalog_query_gateway: CatalogQueryGateway,
        cart_summary_view_mapper: CartSummaryViewMapper,
    ) -> None:
        self._cart_provider: Final[CartProvider] = cart_provider
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway
        self._cart_summary_view_mapper: Final[CartSummaryViewMapper] = (
            cart_summary_view_mapper
        )

    @override
    async def handle(self, command: AddToCartCommand) -> CartSummaryView:
        product_id = ProductId(value=command.product_id)

        if not await self._catalog_query_gateway.product_exists(product_id):
            msg = f"Product '{product_id}' is no longer in the catalog."
            raise ProductNotFoundError(msg)

        cart = await self._cart_provider.current_or_new()
        cart.add_item(product_id, Quantity(value=command.quantity))

        return self._cart_summary_view_mapper.to_view(cart, product_id)
