from dataclasses import dataclass
from uuid import UUID

from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class ScheduleOrderHandoverCommand(Command[bool]):
    """Queue a freshly placed order for handing over to the site (ADR-0004).

    Sent by the consumer of ``OrderPlaced``. No inbox claim: the order id is
    the primary key of the queue, so a redelivered event schedules nothing
    twice without any bookkeeping of messages.
    """

    order_id: UUID
