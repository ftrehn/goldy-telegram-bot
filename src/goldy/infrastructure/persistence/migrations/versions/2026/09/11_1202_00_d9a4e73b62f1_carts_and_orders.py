"""carts and orders: the order number sequence, carts, cart items, orders, order items

Revision ID: d9a4e73b62f1
Revises: c5f28ae01b64
Create Date: 2026-09-11 12:02:00.000000

The sequence name and its start are not decorative. ``nextval`` is called on
``orders_number_seq`` by ``PostgresOrderNumberGenerator``, which holds the same
two values as constants, so a different name here fails the first checkout in
the shop. The start is 1000 because ``OrderNumber`` insists on four digits, and
a first order numbered 1 would be refused by the value object that has to build
it.

``uq_carts_user_id`` is load-bearing in the same way: ``ensure_for`` inserts
with ``ON CONFLICT (user_id) DO NOTHING``, which Postgres resolves against a
unique index and rejects outright without one.

``payment_confirmed_at`` and ``payment_confirmed_by`` are created empty and
stay empty. There is no ``PAID`` status, no domain method and no command that
writes them — the owner's decision that settlement happens outside the bot is
untouched. They exist because the question "does a manager need a paid flag"
had this migration as its deadline: a nullable column costs nothing today and
an ``ALTER`` over a live orders table costs plenty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a4e73b62f1"
down_revision: str | Sequence[str] | None = "c5f28ae01b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE orders_number_seq START WITH 1000")

    op.create_table(
        "carts",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_carts"),
        sa.UniqueConstraint("user_id", name="uq_carts_user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_carts_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "cart_items",
        sa.Column("cart_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cart_id", "product_id", name="pk_cart_items"),
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            name="fk_cart_items_cart_id_carts",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.String(length=16), nullable=False),
        sa.Column("customer_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("price_type_id", sa.String(length=128), nullable=False),
        sa.Column("delivery_address", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("recipient_first_name", sa.String(length=100), nullable=False),
        sa.Column("recipient_last_name", sa.String(length=100), nullable=True),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False),
        sa.Column("cancelled_by", sa.String(length=20), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("payment_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_confirmed_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        sa.UniqueConstraint("number", name="uq_orders_number"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name="fk_orders_customer_id_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=True),
        sa.Column("unit_name", sa.String(length=32), nullable=False),
        sa.Column(
            "unit_price_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column("unit_price_currency", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("order_id", "position", name="pk_order_items"),
        sa.CheckConstraint(
            "unit_price_amount >= 0",
            name="ck_order_items_unit_price_amount_non_negative",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_items_order_id_orders",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("order_items")

    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")

    op.drop_table("cart_items")
    op.drop_table("carts")

    op.execute("DROP SEQUENCE orders_number_seq")
