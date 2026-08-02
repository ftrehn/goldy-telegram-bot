from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    UUID as SA_UUID,
    Column,
    DateTime,
    String,
    Table,
    Text,
)

from goldy.infrastructure.persistence.models.base import mapper_registry


@dataclass
class OutboxRecord:
    """Infrastructure-level mutable dataclass mapped to ``outbox_messages`` table."""

    id: UUID
    event_type: str
    payload: str
    created_at: datetime
    processed_at: datetime | None = None


outbox_messages_table = Table(
    "outbox_messages",
    mapper_registry.metadata,
    Column("id", SA_UUID(as_uuid=True), primary_key=True),
    Column("event_type", String(255), nullable=False, index=True),
    Column("payload", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("processed_at", DateTime(timezone=True), nullable=True),
)


def map_outbox_table() -> None:
    mapper_registry.map_imperatively(
        OutboxRecord,
        outbox_messages_table,
        properties={
            "id": outbox_messages_table.c.id,
            "event_type": outbox_messages_table.c.event_type,
            "payload": outbox_messages_table.c.payload,
            "created_at": outbox_messages_table.c.created_at,
            "processed_at": outbox_messages_table.c.processed_at,
        },
    )
