from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.carts import CartQueryGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.views.cart import CartView
from goldy.application.common.views.money import MoneyView
from goldy.application.queries.carts.get_cart.query import GetCartQuery


class GetCartHandler(QueryHandler[GetCartQuery, CartView]):
    """Reads the caller's cart with prices, stock and a total joined in.

    **Never raises ``CartNotFoundError``.** A cart row is created lazily on the
    first addition, so somebody who has just registered has none at all, and an
    error here would greet every new customer on their first ``/cart``. No row
    means an empty view: no lines and a zero total, which the screen draws as
    "your cart is empty" with a button into the catalog.

    Nothing is priced in Python. The gateway joins the prices and the stock in
    SQL under this customer's price type, which is what makes a new price list
    reprice a standing cart at once instead of leaving old numbers in it. Lines
    whose product has left the catalog come back marked rather than dropped —
    a total that quietly shrinks is worse than one that explains itself.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        price_type_provider: PriceTypeProvider,
        cart_query_gateway: CartQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._cart_query_gateway: Final[CartQueryGateway] = cart_query_gateway

    @override
    async def handle(self, query: GetCartQuery) -> CartView:
        user_id = await self._identity_provider.get_current_user_id()
        price_type_id = await self._price_type_provider.current()

        view = await self._cart_query_gateway.read_for(user_id, price_type_id)

        if view is None:
            return CartView(lines=(), total=MoneyView.zero())

        return view
