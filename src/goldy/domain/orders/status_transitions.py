from collections.abc import Mapping
from typing import Final

from goldy.domain.orders.values.order_status import OrderStatus

ALLOWED_ORDER_TRANSITIONS: Final[Mapping[OrderStatus, frozenset[OrderStatus]]] = {
    OrderStatus.NEW: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}
"""Which status an order may move to from each of its states.

The single source of truth about the lifecycle, written as a table for the same
reason ``SUBORDINATE_ROLES`` is: an ``if`` chain spread over five methods is
five places to disagree with each other.

Terminality falls out of the table rather than being asserted again — the empty
sets on ``COMPLETED`` and ``CANCELLED`` already refuse every move out of them,
so there is no separate "cannot leave a finished order" check anywhere.

Cancelling a ``SHIPPED`` order is allowed on purpose: a courier does come back
with the parcel, and a lifecycle that cannot express it forces staff to record
the truth somewhere the system cannot see.
"""

CUSTOMER_CANCELLABLE_STATUSES: Final[frozenset[OrderStatus]] = frozenset(
    {OrderStatus.NEW, OrderStatus.CONFIRMED},
)
"""The statuses a customer may cancel their own order in.

A manager may cancel anything not yet finished; a customer only an order that
has not left the shop. Confirmation does not take the right to change their
mind away from the buyer — it only means the order was accepted for picking.
After ``SHIPPED`` it would be a return, and returns do not live in the bot.

Read by the order view as well, so the cancel button hides by exactly the rule
the aggregate refuses by — the alternative is a second description of
cancellation living in presentation.
"""

EDITABLE_ORDER_STATUSES: Final[frozenset[OrderStatus]] = frozenset(
    {OrderStatus.NEW, OrderStatus.CONFIRMED},
)
"""The statuses in which order details may still be changed.

Once the parcel is in transit the address on it is already printed, so editing
it in the database would only make the two disagree.
"""

TERMINAL_ORDER_STATUSES: Final[frozenset[OrderStatus]] = frozenset(
    {OrderStatus.COMPLETED, OrderStatus.CANCELLED},
)
"""The statuses an order never leaves — the keys with no transitions left."""
