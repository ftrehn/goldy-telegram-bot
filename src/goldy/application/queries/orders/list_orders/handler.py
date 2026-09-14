from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.query_params.order_filters import (
    OrderFilters,
    OrderSorting,
)
from goldy.application.common.query_params.pagination import Pagination
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.order import OrderListView
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.permission import IsStaff, StaffContext


class ListOrdersHandler(QueryHandler[ListOrdersQuery, OrderListView]):
    """Reads a page of every customer's orders, for the staff queue.

    Guarded by ``IsStaff`` rather than by ``CanManageOrders``: the latter
    answers a question about one order and a list has none to ask it about.
    Reading the queue is how staff find work, and acting on a particular order
    is authorised separately, where there is an order to authorise against.

    Rows carry the customer's name and whether they are blocked. Blocking is
    about access and not about obligations, so an order placed before one can
    perfectly well go on to be confirmed — the queue draws a badge and the
    manager decides.
    """

    def __init__(
        self,
        user_provider: UserProvider,
        order_query_gateway: OrderQueryGateway,
        access_service: AccessService,
    ) -> None:
        self._user_provider: Final[UserProvider] = user_provider
        self._order_query_gateway: Final[OrderQueryGateway] = order_query_gateway
        self._access_service: Final[AccessService] = access_service

    @override
    async def handle(self, query: ListOrdersQuery) -> OrderListView:
        """One page of the queue.

        Raises:
            AuthorizationError: the caller is not staff.
            PaginationError: the page is not a page.
        """
        subject = await self._user_provider.current()
        self._access_service.authorize(
            IsStaff(),
            context=StaffContext(subject=subject),
        )

        return await self._order_query_gateway.read_all(
            pagination=Pagination(limit=query.limit, offset=query.offset),
            sorting=OrderSorting(sort_by=query.sort_by, order=query.order),
            filters=OrderFilters(status=query.status),
        )
