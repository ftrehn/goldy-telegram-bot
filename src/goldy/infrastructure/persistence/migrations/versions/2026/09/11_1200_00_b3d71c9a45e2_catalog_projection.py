"""catalog projection: categories, products, price types, prices, stock, bindings

Revision ID: b3d71c9a45e2
Revises: 8f1c4a2be7d0
Create Date: 2026-09-11 12:00:00.000000

The projection and nothing else. The three GIN indexes the storefront searches
through need ``pg_trgm``, and a managed database may refuse the extension to a
non-superuser; they are therefore created by the next revision, so that a
refusal fails one revision with an obvious cause and leaves this schema
applied.

There is not one foreign key here, in either direction. Rows arrive from 1C
over RabbitMQ in no particular order, so a key would reject a price whose
product has not landed yet — ADR-0002.

The three generated columns are spelled out rather than imported from
``models.catalog_search``. A migration is a frozen record of what was applied,
and one that read a live constant would silently describe something else the
day that constant changed.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3d71c9a45e2"
down_revision: str | Sequence[str] | None = "8f1c4a2be7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

YO: Final[str] = "\N{CYRILLIC SMALL LETTER IO}"
YE: Final[str] = "\N{CYRILLIC SMALL LETTER IE}"
"""Written as escapes, because a Cyrillic "ie" and a Latin "e" look identical.

The mirror of this rule in ``models.catalog_search`` says the same thing for
the same reason: a fold written with the wrong letter folds nothing while
reading as correct.
"""

SKU_NORMALIZED_SQL: Final[str] = "upper(translate(sku, '-_ ./', ''))"
NAME_NORMALIZED_SQL: Final[str] = f"translate(lower(name), '{YO}', '{YE}')"
SEARCH_VECTOR_SQL: Final[str] = f"to_tsvector('russian', {NAME_NORMALIZED_SQL})"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "catalog_categories",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("parent_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_categories"),
    )
    op.create_index(
        "ix_catalog_categories_parent_id",
        "catalog_categories",
        ["parent_id"],
    )
    op.create_index("ix_catalog_categories_path", "catalog_categories", ["path"])

    op.create_table(
        "catalog_products",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("category_id", sa.String(length=128), nullable=True),
        sa.Column("unit_id", sa.String(length=128), nullable=True),
        sa.Column("unit_name", sa.String(length=32), nullable=False),
        sa.Column(
            "unit_ratio",
            sa.Numeric(precision=14, scale=3),
            server_default="1",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "sku_normalized",
            sa.String(length=64),
            sa.Computed(SKU_NORMALIZED_SQL, persisted=True),
            nullable=True,
        ),
        sa.Column(
            "name_normalized",
            sa.String(length=255),
            sa.Computed(NAME_NORMALIZED_SQL, persisted=True),
            nullable=False,
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(SEARCH_VECTOR_SQL, persisted=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_products"),
    )
    op.create_index(
        "ix_catalog_products_category_id",
        "catalog_products",
        ["category_id"],
    )

    op.create_table(
        "catalog_price_types",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_supported", sa.Boolean(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_price_types"),
    )

    op.create_table(
        "catalog_prices",
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("price_type_id", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "product_id",
            "price_type_id",
            name="pk_catalog_prices",
        ),
        sa.CheckConstraint(
            "amount >= 0",
            name="ck_catalog_prices_amount_non_negative",
        ),
    )
    op.create_index(
        "ix_catalog_prices_price_type_id",
        "catalog_prices",
        ["price_type_id"],
    )

    op.create_table(
        "catalog_stock",
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("warehouse_id", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "product_id",
            "warehouse_id",
            name="pk_catalog_stock",
        ),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_catalog_stock_quantity_non_negative",
        ),
    )

    op.create_table(
        "catalog_price_type_bindings",
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("price_type_id", sa.String(length=128), nullable=False),
        sa.Column("source_counterparty_id", sa.String(length=128), nullable=True),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("source_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "phone_number",
            name="pk_catalog_price_type_bindings",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("catalog_price_type_bindings")

    op.drop_table("catalog_stock")

    op.drop_index("ix_catalog_prices_price_type_id", table_name="catalog_prices")
    op.drop_table("catalog_prices")

    op.drop_table("catalog_price_types")

    op.drop_index("ix_catalog_products_category_id", table_name="catalog_products")
    op.drop_table("catalog_products")

    op.drop_index("ix_catalog_categories_path", table_name="catalog_categories")
    op.drop_index("ix_catalog_categories_parent_id", table_name="catalog_categories")
    op.drop_table("catalog_categories")
