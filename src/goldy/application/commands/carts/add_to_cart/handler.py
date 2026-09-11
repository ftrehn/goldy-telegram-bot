from typing import Final, override

from goldy.application.commands.carts.add_to_cart.command import AddToCartCommand
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.carts import CartCommandGateway
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.mappers import CartSummaryViewMapper
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

    Creating the cart goes through ``ensure_for`` rather than a read followed
    by an insert. Two simultaneous first additions both find nothing and both
    insert, and the retry that would repair it cannot be written here: after an
    ``IntegrityError`` the session is rollback-only and the next statement
    fails with ``PendingRollbackError``.
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
    async def handle(self, command: AddToCartCommand) -> CartSummaryView:
        user_id = await self._identity_provider.get_current_user_id()
        product_id = ProductId(value=command.product_id)

        if not await self._catalog_query_gateway.product_exists(product_id):
            msg = f"Product '{product_id}' is no longer in the catalog."
            raise ProductNotFoundError(msg)

        cart = await self._cart_command_gateway.ensure_for(user_id)
        cart.add_item(product_id, Quantity(value=command.quantity))

        return self._cart_summary_view_mapper.to_view(cart, product_id)
