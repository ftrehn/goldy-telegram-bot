"""notifications inbox: the table that stops one order being announced twice

Revision ID: e1c07f4a92d3
Revises: d9a4e73b62f1
Create Date: 2026-09-11 12:03:00.000000

The mirror of ``outbox_messages`` at the receiving end, and the primary key is
the whole mechanism. ``id`` holds the outbox row's own id, which travels as the
AMQP ``message_id`` and does not change when the relay republishes a message it
had already sent — so ``INSERT ... ON CONFLICT (id) DO NOTHING`` is what decides
whether this delivery is the first one. There is no separate unique index to add
and no deduplication in application code: the constraint is the decision.

No foreign key to ``outbox_messages``. The two tables are the two ends of a
broker, not a parent and a child: a message can be consumed after its outbox row
has been pruned, and the reference would turn ordinary housekeeping into a
failing insert on the consumer side.

``ix_inbox_messages_processed_at`` is for pruning, which this table will need.
Rows are worth keeping only as long as a message can still be redelivered —
days, not years — and a delete by date without the index is a sequential scan
over every notification ever sent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1c07f4a92d3"
down_revision: str | Sequence[str] | None = "d9a4e73b62f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "inbox_messages",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_inbox_messages"),
    )

    op.create_index(
        "ix_inbox_messages_processed_at",
        "inbox_messages",
        ["processed_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_inbox_messages_processed_at", table_name="inbox_messages")
    op.drop_table("inbox_messages")
