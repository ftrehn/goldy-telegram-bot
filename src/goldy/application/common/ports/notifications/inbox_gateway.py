from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class InboxGateway(Protocol):
    """Record of the broker messages this service has already acted on.

    The counterpart of the outbox, and it exists for the same reason seen from
    the other end. The relay publishes at least once — a message is marked
    processed only after the transport accepted it, so a crash between the two
    re-sends it — which means a consumer that simply did the work would write
    to somebody twice about one order.

    The key is ``OutboxMessage.id``. It is the outbox row's primary key and the
    event's own identity, so it is stable across every retry and across the
    relay being restarted; nothing else about a redelivered message is.

    Write-side only, and there is no read method. "Has this been handled" and
    "mark it handled" are one decision taken under one lock, and splitting them
    into a read and a write is how two workers both decide they are the first.
    """

    @abstractmethod
    async def claim(self, message_id: UUID, event_type: str) -> bool:
        """Take responsibility for a message, if nobody has yet.

        Returns True when this caller is the first to see ``message_id`` and
        should therefore do the work, False when the message was handled
        before and must be dropped.

        The claim belongs to the caller's transaction. Committing it together
        with whatever the message caused is what makes the pair atomic — and
        what makes a rollback put the message back up for grabs.
        """
        raise NotImplementedError
