from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from goldy.application.common.mediator.markers import Command


class HandoverOutcome(StrEnum):
    """What one attempt at handing an order over came to."""

    ACCEPTED = "accepted"
    RETRY = "retry"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class HandOverOrderCommand(Command[HandoverOutcome]):
    """Hand one queued order over to the site, in a transaction of its own."""

    order_id: UUID
