"""site links and order handovers: the bot's half of the site API (ADR-0004)

Revision ID: f4a8c21d6b90
Revises: e1c07f4a92d3
Create Date: 2026-09-25 12:00:00.000000

``user_site_links`` is the bot's copy of a person's link to their customer
account on tkgoldy.ru. The site owns the link; the copy exists so that a
retail customer's cart is not a round trip to the site. One row per person,
keyed by the user, cascading with them.

``order_handovers`` records which orders the site has been given and which it
still has to get. The order id is the primary key and the whole of the
idempotency of scheduling: the consumer of ``OrderPlaced`` inserts with
``ON CONFLICT DO NOTHING``, so a redelivered event schedules nothing twice.
The two indexes serve the only two questions asked of the table on a
schedule: which pending handovers are due, and where the order feed stopped.

Orders placed before this revision are not scheduled. They predate the
handover, their managers already have them, and sending weeks-old orders to
the site on the first run would be a surprise nobody asked for.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a8c21d6b90"
down_revision: str | Sequence[str] | None = "e1c07f4a92d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_site_links",
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_name", sa.String(length=200), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("is_wholesale", sa.Boolean(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_site_links_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_site_links"),
    )

    op.create_table(
        "order_handovers",
        sa.Column("order_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("site_order_id", sa.Integer(), nullable=True),
        sa.Column("site_number", sa.String(length=64), nullable=True),
        sa.Column("site_status_code", sa.String(length=20), nullable=True),
        sa.Column("site_status_name", sa.String(length=255), nullable=True),
        sa.Column("site_state", sa.String(length=20), nullable=True),
        sa.Column("site_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_handovers_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("order_id", name="pk_order_handovers"),
    )
    op.create_index(
        "ix_order_handovers_due",
        "order_handovers",
        ["state", "next_attempt_at"],
    )
    op.create_index(
        "ix_order_handovers_site_updated_at",
        "order_handovers",
        ["site_updated_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_order_handovers_site_updated_at", table_name="order_handovers")
    op.drop_index("ix_order_handovers_due", table_name="order_handovers")
    op.drop_table("order_handovers")
    op.drop_table("user_site_links")
