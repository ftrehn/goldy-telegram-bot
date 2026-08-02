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

    The outbox row reuses the event's own identity and timestamp rather than
    minting new ones, so re-serializing the same event yields the same row:
    the relay's at-least-once delivery then cannot turn one domain fact into
    two messages that consumers see as unrelated.
    """

    @override
    def serialize(self, event: Event) -> OutboxMessage:
        return OutboxMessage(
            id=event.event_id,
            event_type=event.event_type,
            payload=json.dumps(_retort.dump(event)),
            created_at=event.event_date,
        )
