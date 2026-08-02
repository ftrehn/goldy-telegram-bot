from dataclasses import dataclass
from datetime import datetime

from .event_id import EventId


@dataclass(frozen=True, kw_only=True)
class Event:
    event_id: EventId
    event_date: datetime

    @property
    def event_type(self) -> str:
        return self.__class__.__name__
