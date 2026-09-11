from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.query_params.order_filters import OrderSortField
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.order import OrderListView
from goldy.domain.orders.values.order_status import OrderStatus


@dataclass(frozen=True, slots=True)
class ListMyOrdersQuery(Query[OrderListView]):
    """One page of the caller's own order history, newest first.

    There is no customer field and there will not be one. Whose history this is
    comes from the identity provider inside the handler, so there is physically
    nothing to put a stranger's identifier into — which is a stronger guarantee
    than any check that could be written here.

    Finished orders are in the page by default. "Where is the order I placed
    last spring" is an ordinary question, and :attr:`status` is a button
    somebody presses rather than a behaviour.
    """

    limit: int | None = None
    offset: int | None = None
    status: OrderStatus | None = None
    sort_by: OrderSortField = OrderSortField.CREATED_AT
    order: SortingOrder = SortingOrder.DESC
