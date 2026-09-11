from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.query_params.order_filters import (
    OrderFilters,
    OrderSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.views.order import OrderListView
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery


class ListMyOrdersHandler(QueryHandler[ListMyOrdersQuery, OrderListView]):
    """Reads a page of the caller's own orders.

    Takes the identity provider rather than ``UserProvider``: this needs an
    identifier to filter by and not the aggregate, and loading a user to read a
    field off it would be a second query for nothing. That identifier is also
    the security boundary here — the query carries no customer field, so there
    is nothing to substitute.

    No ``AccessService`` either. There is no rule about who may read their own
    history, and the auth gate has already turned away anyone unregistered or
    blocked before a query reaches this layer.

    The unpaginated total comes back with the page, because a pager that knows
    only its own slice cannot say how many pages there are.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        order_query_gateway: OrderQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._order_query_gateway: Final[OrderQueryGateway] = order_query_gateway

    @override
    async def handle(self, query: ListMyOrdersQuery) -> OrderListView:
        """One page of orders belonging to whoever is asking.

        Raises:
            AuthenticationError: the account writing to us belongs to nobody.
            PaginationError: the page is not a page.
        """
        customer_id = await self._identity_provider.get_current_user_id()

        return await self._order_query_gateway.read_for_customer(
            customer_id=customer_id,
            pagination=Pagination(limit=query.limit, offset=query.offset),
            sorting=OrderSorting(sort_by=query.sort_by, order=query.order),
            filters=OrderFilters(status=query.status),
        )
