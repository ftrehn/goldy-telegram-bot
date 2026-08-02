"""Builders for outbox rows.

For tests that care about the relay rather than about which event happened to
be in the row.
"""

import json
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any, Final
from uuid import UUID, uuid4

from goldy.application.common.ports.outbox import OutboxMessage

DEFAULT_EVENT_TYPE: Final[str] = "UserRegistered"

FIRST_CREATED_AT: Final[datetime] = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

_SEQUENCE: Final[count[int]] = count()


def make_outbox_message(
    event_type: str = DEFAULT_EVENT_TYPE,
    payload: dict[str, Any] | None = None,
    message_id: UUID | None = None,
    created_at: datetime | None = None,
) -> OutboxMessage:
    """One pending message, later than every message built before it.

    ``created_at`` advances a second per call rather than being ``now()``: the
    relay hands messages back oldest first, and a test of that ordering needs
    the order to be a fact rather than a race between two rows written in the
    same microsecond.
    """
    index = next(_SEQUENCE)

    return OutboxMessage(
        id=message_id if message_id is not None else uuid4(),
        event_type=event_type,
        payload=json.dumps(payload if payload is not None else {"sequence": index}),
        created_at=(
            created_at
            if created_at is not None
            else FIRST_CREATED_AT + timedelta(seconds=index)
        ),
    )
