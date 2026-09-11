from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from goldy.application.common.views.money import MoneyView


@dataclass(frozen=True, slots=True)
class OrderLineView:
    """One line of a placed order, read back exactly as it was agreed.

    Everything printed here is the snapshot the line was created with, never a
    lookup through ``product_id``: the catalog is a projection of 1C and will
    have moved on — a renamed product, a corrected article, a new price — while
    the order has to keep showing what was bought.

    ``stock`` is the one exception, and it is not part of the order at all. The
    staff card joins the current stock so a manager deciding whether to confirm
    can see what is on the shelf next to what was ordered; the customer's own
    card leaves it unset.
    """

    position: int
    product_id: str
    sku: str | None
    name: str
    unit_name: str
    quantity: int
    unit_price: MoneyView
    line_total: MoneyView
    stock: Decimal | None


@dataclass(frozen=True, slots=True)
class OrderView:
    """An order card, for the customer who placed it and for staff.

    One view for both audiences because it is one card. Who is allowed to open
    it is not decided here and not decided by which fields are present: the
    query authorises with ``AnyOf(IsOrderOwner(), CanManageOrders())`` over
    :attr:`customer_id` before this ever reaches a screen.

    The three flags are computed by the row mapper against
    ``CUSTOMER_CANCELLABLE_STATUSES``, ``EDITABLE_ORDER_STATUSES`` and
    ``TERMINAL_ORDER_STATUSES``. This view is assembled from a ``RowMapping``
    rather than from the aggregate, so the alternative would be a second
    statement of the cancellation rule spelled ``status == "new"``, and that
    one drifts away from the aggregate on the first edit and drifts silently.

    :attr:`customer_is_blocked` is a fact for the manager to weigh, not a rule.
    Blocking is about access rather than about obligations, and an order placed
    before the block can perfectly well go on to be confirmed — the queue draws
    a badge and the person decides.
    """

    id: UUID
    number: str
    customer_id: UUID
    customer_is_blocked: bool
    status: str
    price_type_id: str
    delivery_address: str
    recipient_first_name: str
    recipient_last_name: str | None
    recipient_phone_number: str
    comment: str | None
    cancelled_by: str | None
    cancellation_reason: str | None
    lines: tuple[OrderLineView, ...]
    total: MoneyView
    is_cancellable: bool
    is_editable: bool
    is_terminal: bool
    created_at: datetime
    updated_at: datetime

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def total_quantity(self) -> int:
        return sum(line.quantity for line in self.lines)


@dataclass(frozen=True, slots=True)
class OrderListItemView:
    """One row of an order list, for the customer's history or the staff queue.

    :attr:`total` is summed in SQL rather than by loading aggregates: the
    property on ``Order`` computes the same number from the same lines, but a
    list of orders exists to be printed and loading fifty aggregates with their
    lines to print fifty numbers is how the queue gets slow.

    The customer fields are populated for both audiences — the join is on a
    primary key and costs nothing — and the customer's own history simply does
    not draw them.
    """

    id: UUID
    number: str
    customer_id: UUID
    customer_name: str | None
    customer_is_blocked: bool
    status: str
    total: MoneyView
    line_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OrderListView:
    """One page of orders together with the count the pager needs."""

    orders: tuple[OrderListItemView, ...]
    total: int


@dataclass(frozen=True, slots=True)
class OrderPlacedView:
    """What placing an order hands back — the number and nothing else.

    No aggregate-to-view mapper exists for orders, and this is why: the card is
    shown by ``GetOrderQuery``, not by the handler that placed the order, so an
    adapter built for a single call would only have added a sixth collaborator
    to a handler that already has five. The "done" screen needs to name the
    number and to be able to open the card as its next step.
    """

    order_id: UUID
    order_number: str
