from dataclasses import dataclass
from uuid import UUID

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class NotifyOrderStatusChangedCommand(Command[NotificationOutcome]):
    """Tell the buyer their order moved, cancellation included.

    Everything the message needs is in the event, so no order is read here.
    The number is what the person calls the order, the status is what changed,
    and the reason is the text they are owed when it was cancelled — those
    three and the customer id are exactly what ``OrderStatusChanged`` carries.

    ``old_status`` is not among them. "Confirmed → shipped" is a sentence for a
    log, not for a customer, who wants to know where the parcel is now.
    """

    message_id: UUID
    order_number: str
    customer_id: UUID
    new_status: str
    reason: str | None = None
