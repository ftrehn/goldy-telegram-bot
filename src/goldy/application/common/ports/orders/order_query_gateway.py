from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.query_params.order_filters import (
        OrderFilters,
        OrderSorting,
    )
    from goldy.application.common.query_params.pagination import Pagination
    from goldy.application.common.views.order import OrderListView, OrderView
    from goldy.domain.orders.values.order_id import OrderId
    from goldy.domain.users.values.user_id import UserId


class OrderQueryGateway(Protocol):
    """Read-side DAO for order cards, a customer's history and the staff queue.

    Returns views, never aggregates. A list row needs a number, a date, a
    status and a total, and the total is summed in SQL: ``Order.total`` gets
    the same number out of the same lines, but loading fifty aggregates with
    their lines to print fifty numbers is how the queue gets slow.

    Two listing methods rather than one with an owner filter, because the
    difference is a security boundary rather than a parameter. The customer's
    own history takes its id from the identity provider, so there is physically
    nothing to put somebody else's id into — which is stronger than any check.

    A card is read before it is authorised, which is why :meth:`read_by_id`
    refuses nobody: the view carries ``customer_id``, and the query decides
    with ``AnyOf(IsOrderOwner(), CanManageOrders())`` over it.
    """

    @abstractmethod
    async def read_by_id(self, order_id: OrderId) -> OrderView | None:
        """One order card, for whoever turns out to be allowed to see it."""
        raise NotImplementedError

    @abstractmethod
    async def read_for_customer(
        self,
        *,
        customer_id: UserId,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        """One page of this person's own orders, newest first by default.

        Finished orders are in it. "Where is the order I placed last spring" is
        an ordinary question, and filtering by status is a button rather than a
        default.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_all(
        self,
        *,
        pagination: Pagination,
        sorting: OrderSorting,
        filters: OrderFilters,
    ) -> OrderListView:
        """One page of the staff queue, across every customer."""
        raise NotImplementedError

    @abstractmethod
    async def read_last_delivery_address(self, customer_id: UserId) -> str | None:
        """Where this person's most recent order went, or nothing.

        Offered as a button on the address screen, so a repeat order is an
        address tap, a recipient tap and a confirmation. One more column on a
        query this gateway already runs for the history.
        """
        raise NotImplementedError
