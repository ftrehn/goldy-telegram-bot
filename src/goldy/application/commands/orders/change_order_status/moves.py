"""One strategy per status a manager can move an order to.

A table of small objects rather than a ``match`` inside the handler, for the
reason ``ALLOWED_ORDER_TRANSITIONS`` is a table: every move calls a different
aggregate method with different preconditions and different arguments, and a
branch per status inside one method grows by a branch on every new status until
nobody wants to read it. Here a new status is a new class and one more line in
:data:`MOVES`; the handler does not change.

The strategies are stateless, so the table holds instances rather than classes
and the handler looks one up by the status the command names. ``NEW`` is absent
on purpose: nothing in ``ALLOWED_ORDER_TRANSITIONS`` leads back to it, an order
cannot be un-confirmed, and the handler treats a status with no strategy as
exactly that refusal.
"""

from abc import abstractmethod
from collections.abc import Mapping
from typing import Final, Protocol, final, override

from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.entities.user import User


class OrderMove(Protocol):
    """Applies one transition to an order, on behalf of a member of staff."""

    @abstractmethod
    def apply(self, order: Order, *, actor: User, reason: str | None) -> None:
        raise NotImplementedError


@final
class Confirm(OrderMove):
    @override
    def apply(self, order: Order, *, actor: User, reason: str | None) -> None:
        order.confirm()


@final
class Ship(OrderMove):
    @override
    def apply(self, order: Order, *, actor: User, reason: str | None) -> None:
        order.ship()


@final
class Complete(OrderMove):
    @override
    def apply(self, order: Order, *, actor: User, reason: str | None) -> None:
        order.complete()


@final
class CancelAsStaff(OrderMove):
    """The one move that reads the reason and records who did it.

    The reason stays optional here because the rule "a manager must say why"
    belongs to the aggregate: ``Order.cancel`` refuses a manager without one,
    and stating it twice would let the two statements drift apart.
    """

    @override
    def apply(self, order: Order, *, actor: User, reason: str | None) -> None:
        order.cancel(
            initiated_by=CancellationInitiator.MANAGER,
            cancelled_by_user_id=actor.id,
            reason=None if reason is None else CancellationReason(value=reason),
        )


MOVES: Final[Mapping[OrderStatus, OrderMove]] = {
    OrderStatus.CONFIRMED: Confirm(),
    OrderStatus.SHIPPED: Ship(),
    OrderStatus.COMPLETED: Complete(),
    OrderStatus.CANCELLED: CancelAsStaff(),
}
