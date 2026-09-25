from dataclasses import dataclass
from uuid import UUID

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class NotifyOrderHandoverRejectedCommand(Command[NotificationOutcome]):
    """Tell staff the site refused an order, so they pick it up by hand.

    ``message_id`` and ``event_type`` are the inbox's key and label, as for
    every other notification.
    """

    message_id: UUID
    event_type: str
    order_number: str
    code: str
