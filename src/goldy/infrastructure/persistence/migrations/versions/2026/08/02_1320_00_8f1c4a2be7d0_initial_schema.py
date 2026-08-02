"""initial schema: outbox messages, users, messenger accounts

Revision ID: 8f1c4a2be7d0
Revises:
Create Date: 2026-08-02 13:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f1c4a2be7d0"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_messages"),
    )
    op.create_index(
        "ix_outbox_messages_created_at",
        "outbox_messages",
        ["created_at"],
    )
    op.create_index(
        "ix_outbox_messages_event_type",
        "outbox_messages",
        ["event_type"],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("notify_via", sa.String(length=20), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("phone_number", name="uq_users_phone_number"),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "messenger_accounts",
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "platform",
            "external_id",
            name="pk_messenger_accounts",
        ),
        sa.UniqueConstraint(
            "user_id",
            "platform",
            name="uq_messenger_accounts_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_messenger_accounts_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_messenger_accounts_user_id",
        "messenger_accounts",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_messenger_accounts_user_id", table_name="messenger_accounts")
    op.drop_table("messenger_accounts")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_outbox_messages_event_type", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_created_at", table_name="outbox_messages")
    op.drop_table("outbox_messages")
