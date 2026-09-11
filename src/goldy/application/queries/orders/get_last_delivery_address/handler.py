from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)


class GetLastDeliveryAddressHandler(
    QueryHandler[GetLastDeliveryAddressQuery, str | None]
):
    """Reads back the address of the caller's most recent order.

    Exists so the checkout dialog can offer "same place as last time" instead
    of making somebody retype an address they have already given us. With a
    hundred lines allowed in a cart, a repeat order should be an address tap, a
    recipient tap and a confirmation.

    Takes the identity provider rather than ``UserProvider``, exactly as
    ``ListMyOrdersHandler`` does: this needs an identifier to read by and not
    the aggregate behind it, and the identifier is also the security boundary —
    it comes from the session and never from the request.

    No ``AccessService``. There is no rule about who may read their own last
    address, and the auth gate has already turned away anyone unregistered or
    blocked before a query reaches this layer.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        order_query_gateway: OrderQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._order_query_gateway: Final[OrderQueryGateway] = order_query_gateway

    @override
    async def handle(self, query: GetLastDeliveryAddressQuery) -> str | None:
        """The address of the previous order, or nothing on a first one.

        Raises:
            AuthenticationError: the account writing to us belongs to nobody.
        """
        customer_id = await self._identity_provider.get_current_user_id()

        return await self._order_query_gateway.read_last_delivery_address(customer_id)
