from typing import Final

from sqlalchemy import (
    UUID as SA_UUID,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)

from goldy.infrastructure.persistence.models.base import mapper_registry

order_handovers_table: Final[Table] = Table(
    "order_handovers",
    mapper_registry.metadata,
    Column(
        "order_id",
        SA_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("state", String(20), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("error_code", String(64), nullable=True),
    Column("last_error", Text, nullable=True),
    Column("site_order_id", Integer, nullable=True),
    Column("site_number", String(64), nullable=True),
    Column("site_status_code", String(20), nullable=True),
    Column("site_status_name", String(255), nullable=True),
    Column("site_state", String(20), nullable=True),
    Column("site_updated_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_order_handovers_due", "state", "next_attempt_at"),
    Index("ix_order_handovers_site_updated_at", "site_updated_at"),
)
"""Which orders the site has, and which it still has to get (ADR-0004).

The order's integration state, kept beside the order because ``Order``
refuses to carry it: whether the site has the order says nothing about the
goods. The primary key is the order id, and it is the whole of the idempotency
of scheduling — a second delivery of ``OrderPlaced`` inserts nothing.

No mapping and no dataclass: nothing loads a handover as an object. The DAO
reads and writes rows, and the table's presence in the metadata is what makes
alembic see it.

``ix_order_handovers_due`` serves "pending and due", the one query the
handover runs every minute; ``ix_order_handovers_site_updated_at`` serves
"the newest change the feed delivered", which is where the next pass of the
order feed starts.
"""
