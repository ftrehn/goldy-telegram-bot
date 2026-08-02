import json
from datetime import datetime
from typing import Final, final, override
from uuid import UUID

from adaptix import Retort, dumper

from goldy.application.common.ports.outbox import (
    EventSerializer,
    OutboxMessage,
)
from goldy.domain.common.event import Event

_retort: Final[Retort] = Retort(
    recipe=[
        dumper(UUID, str),
        dumper(datetime, datetime.isoformat),
    ],
)


@final
class RetortEventSerializer(EventSerializer):
    """Renders domain events as JSON outbox rows via adaptix.

    Stamps the event with its identity and timestamp first: both setters are
    write-once, so re-serializing an already-stamped event keeps the original
    values and the payload stays byte-identical.
    """

    @override
    def serialize(self, event: Event) -> OutboxMessage:

        return OutboxMessage(
            id=event.event_id,
            event_type=event.event_type,
            payload=json.dumps(_retort.dump(event)),
            created_at=event.event_date,
        )
