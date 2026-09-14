from dataclasses import dataclass
from enum import StrEnum

from goldy.application.common.query_params.sorting import SortingOrder
from goldy.domain.orders.values.order_status import OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderFilters:
    """Narrows an order list. Unset means "every order in scope".

    Finished orders are not hidden by default, and the default is the point:
    "where is the order I placed last spring" is an ordinary question, and a
    history that silently drops what it considers over cannot answer it.
    Filtering by status is a button somebody presses, not a behaviour.

    There is no customer field. Whose orders are being listed is decided by
    which gateway method is called, and for the customer's own history it comes
    from the identity provider rather than from anything the request carries —
    there is physically nothing to put somebody else's id into.
    """

    status: OrderStatus | None = None


class OrderSortField(StrEnum):
    """What an order list is ordered by."""

    CREATED_AT = "created_at"
    NUMBER = "number"


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSorting:
    """How an order list is ordered.

    Newest first by default, for both audiences: a customer opens their history
    to find what they just ordered, and a manager opens the queue to find what
    just arrived.
    """

    sort_by: OrderSortField = OrderSortField.CREATED_AT
    order: SortingOrder = SortingOrder.DESC
