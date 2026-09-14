from typing import Final

from sqlalchemy import (
    UUID as SA_UUID,
    Column,
    DateTime,
    String,
    Table,
)

from goldy.infrastructure.persistence.models.base import mapper_registry

inbox_messages_table: Final[Table] = Table(
    "inbox_messages",
    mapper_registry.metadata,
    Column("id", SA_UUID(as_uuid=True), primary_key=True),
    Column("event_type", String(255), nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=False, index=True),
)
"""One row per broker message this service has already acted on.

The mirror of ``outbox_messages`` at the receiving end. ``id`` is the outbox
row's own primary key, travelling as the AMQP ``message_id``, which makes it
stable across redeliveries and across a restart of the relay — the one property
an idempotency key has to have.

No table-level mapping and no dataclass, unlike ``OutboxRecord``. Nothing ever
loads an inbox row: the only operation is a conditional insert whose row count
answers "was I first", and an identity map for rows nobody reads back would
only grow the session. Its presence in ``mapper_registry.metadata`` is what
makes alembic see it.

``processed_at`` is indexed for the pruning this table will eventually need.
Rows are only worth keeping as long as a message can still be redelivered,
which is days rather than years, and a delete by date with no index behind it
is a sequential scan over everything that ever happened.
"""
