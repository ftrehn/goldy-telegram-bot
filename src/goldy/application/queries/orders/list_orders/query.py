from dataclasses import dataclass

from goldy.application.common.mediator.markers import Query
from goldy.application.common.query_params.order_filters import OrderSortField
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.order import OrderListView
from goldy.domain.orders.values.order_status import OrderStatus


@dataclass(frozen=True, slots=True)
class ListOrdersQuery(Query[OrderListView]):
    """One page of the staff queue, across every customer.

    A separate query from ``ListMyOrdersQuery`` rather than the same one with
    an optional customer filter, because the difference between them is a
    security boundary and not a parameter: one of them takes the customer from
    the identity provider and cannot be pointed elsewhere, and the other is
    guarded by ``IsStaff``. Folding them together would make the guard the only
    thing between a buyer and everybody's orders.

    Newest first, because a manager opens the queue to see what just arrived.
    """

    limit: int | None = None
    offset: int | None = None
    status: OrderStatus | None = None
    sort_by: OrderSortField = OrderSortField.CREATED_AT
    order: SortingOrder = SortingOrder.DESC
