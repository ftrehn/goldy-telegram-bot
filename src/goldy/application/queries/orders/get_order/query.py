from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Query
from goldy.application.common.views.order import OrderView


@dataclass(frozen=True, slots=True)
class GetOrderQuery(Query[OrderView]):
    """One order card, for the buyer who placed it or for staff.

    One query for both audiences rather than two, because it is one card and
    one rule made of two halves — ``AnyOf(IsOrderOwner(), CanManageOrders())``.
    Two queries would mean two places to forget an authorisation.

    Carries only the identifier. Who is asking comes from the identity
    provider, so there is nothing here to put somebody else's name into.
    """

    order_id: UUID
