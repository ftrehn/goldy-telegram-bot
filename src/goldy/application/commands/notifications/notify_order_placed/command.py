from dataclasses import dataclass
from uuid import UUID

from goldy.application.commands.notifications.outcome import NotificationOutcome
from goldy.application.common.mediator.markers import Command


@dataclass(frozen=True, slots=True)
class NotifyOrderPlacedCommand(Command[NotificationOutcome]):
    """Tell the people who work here that a new order is waiting.

    Three fields, and the last one is the whole design. ``OrderPlaced`` carries
    a total, a currency and a line count, and none of them is taken from the
    event: what a manager needs in the message is who ordered, where it goes
    and how to ring them, and those were deliberately kept out of the event so
    that nobody's address and telephone number sit in a queue. The notifier
    reads the order by its id, exactly as the events table in
    ``docs/design/ordering.md`` says it will.

    :attr:`message_id` is ``OutboxMessage.id`` — the broker's ``message_id``,
    stable across every redelivery, and the only thing the inbox keys off.
    :attr:`event_type` is the name the message was published under, carried
    by whoever received it so the inbox records what the claim was for; the
    handler does not guess it from a class it happens to import.
    """

    message_id: UUID
    event_type: str
    order_id: UUID
