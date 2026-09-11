from dataclasses import dataclass
from uuid import UUID

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class NotifyDeliveryAddressChangedCommand(Command[NotificationOutcome]):
    """Tell the buyer their order is going somewhere else now.

    The two addresses come straight from ``OrderDeliveryAddressChanged``, which
    is the one event allowed to carry an address at all: an announcement that
    the parcel moved, without saying where from and where to, announces
    nothing. The old one is not recoverable anywhere else — the aggregate
    remembers only the new one — so "was → now" can be assembled from the event
    and from nothing else.
    """

    message_id: UUID
    order_number: str
    customer_id: UUID
    old_address: str
    new_address: str
