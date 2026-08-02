from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from .event_id import EventId


@dataclass(frozen=True, kw_only=True)
class Event:
    """Something that happened in the domain, recorded by an aggregate.

    Identity and timestamp are stamped at construction rather than at publish
    time, because both are what the outbox row is keyed and ordered by: the
    aggregate is the only place that knows *when* the fact occurred, and the
    relay may only get to it seconds later.

    ``kw_only`` is what lets these defaults sit in the base class without
    forcing every subclass field to have a default of its own.
    """

    event_id: EventId = field(default_factory=lambda: EventId(uuid4()))
    event_date: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        return self.__class__.__name__
