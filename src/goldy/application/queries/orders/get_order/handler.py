from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.orders import OrderQueryGateway
from goldy.application.common.services.user_provider import UserProvider
from goldy.application.common.views.order import OrderView
from goldy.application.error import OrderNotFoundError
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.domain.orders.services.authorization.permission import (
    CanManageOrders,
    IsOrderOwner,
    OrderAccessContext,
)
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.services.authorization.composite import AnyOf
from goldy.domain.users.values.user_id import UserId


class GetOrderHandler(QueryHandler[GetOrderQuery, OrderView]):
    """Reads one order card and decides who was allowed to see it.

    The card is read before it is authorised, which is the only order that
    works: the rule is about whose order this is, and that is a fact of the
    row. Nothing is handed back before ``AnyOf`` has agreed, so the read leaks
    nothing beyond the existence of an identifier the caller already had.

    ``AnyOf`` over two permissions rather than "if staff, else owner": the
    buyer and the manager reach the same card through the same rule, and a
    branch here would be a third statement of who staff are.
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
    async def handle(self, query: GetOrderQuery) -> OrderView:
        """The card, for an owner or for staff.

        Raises:
            OrderNotFoundError: no such order.
            AuthorizationError: the caller is neither its buyer nor staff.
        """
        order_id = OrderId(query.order_id)
        view = await self._order_query_gateway.read_by_id(order_id)

        if view is None:
            msg = f"Order '{order_id}' does not exist."
            raise OrderNotFoundError(msg)

        subject = await self._user_provider.current()
        self._access_service.authorize(
            AnyOf(IsOrderOwner(), CanManageOrders()),
            context=OrderAccessContext(
                subject=subject,
                order_customer_id=UserId(view.customer_id),
            ),
        )

        return view
