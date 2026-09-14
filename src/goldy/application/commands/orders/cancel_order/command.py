from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class CancelOrderCommand(Command[None]):
    """The customer taking back their own order.

    A separate command from ``ChangeOrderStatusCommand`` rather than a branch
    inside it. The two differ in who may run them and in which statuses they
    accept, and an ``if`` choosing between two sets of rules is precisely what
    this project replaced with permissions and a transition table.

    No reason field: somebody withdrawing their own order owes nobody an
    explanation, while a manager cancelling somebody else's does — and that
    asymmetry is held by the aggregate, not here.

    Returns nothing. The card is redrawn by ``GetOrderQuery`` afterwards, so a
    view built inside the write transaction would be a second read paying for
    data the screen throws away.
    """

    order_id: UUID
