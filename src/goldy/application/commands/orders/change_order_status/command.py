from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command
from goldy.domain.orders.values.order_status import OrderStatus


@dataclass(frozen=True, slots=True)
class ChangeOrderStatusCommand(Command[None]):
    """Staff moving an order along, or stopping it.

    One command for all four moves rather than four, because the caller is the
    same person doing the same kind of thing and the table of allowed
    transitions already knows which moves exist. Which move is legal from where
    is answered in one place, ``ALLOWED_ORDER_TRANSITIONS``, and never here.

    :attr:`reason` is only ever read when the target is ``CANCELLED``, and it
    is optional here because the rule "a manager must say why" belongs to the
    aggregate: ``Order.cancel`` refuses a manager without one. Stating it twice
    would let the two statements drift apart.

    There is no ``PAID`` to move to. Settlement happens outside the bot.
    """

    order_id: UUID
    status: OrderStatus
    reason: str | None = None
