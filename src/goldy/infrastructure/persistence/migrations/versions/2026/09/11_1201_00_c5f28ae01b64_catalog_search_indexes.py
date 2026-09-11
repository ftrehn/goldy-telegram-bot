"""catalog search: pg_trgm and the three GIN indexes over the product card

Revision ID: c5f28ae01b64
Revises: b3d71c9a45e2
Create Date: 2026-09-11 12:01:00.000000

A revision of its own, and the split is by what can fail rather than by size.
``CREATE EXTENSION`` needs a privilege managed databases routinely withhold, so
separating it means the refusal lands on exactly the revision whose cause is
obvious: the schema from the previous one stays applied, the shop keeps
working, and search degrades to ``ILIKE`` until somebody grants the extension.

All three indexes are partial on ``is_active`` — a deactivated product is never
searched for — which is what keeps three GIN indexes on one table affordable.

``ix_catalog_products_search_vector`` alone would survive without ``pg_trgm``;
it is created here anyway, so that "search is installed" is one revision and
not one and a half.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f28ae01b64"
down_revision: str | Sequence[str] | None = "b3d71c9a45e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_catalog_products_search_vector",
        "catalog_products",
        ["search_vector"],
        postgresql_using="gin",
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_catalog_products_sku_normalized_trgm",
        "catalog_products",
        ["sku_normalized"],
        postgresql_using="gin",
        postgresql_ops={"sku_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_catalog_products_name_normalized_trgm",
        "catalog_products",
        ["name_normalized"],
        postgresql_using="gin",
        postgresql_ops={"name_normalized": "gin_trgm_ops"},
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    """Downgrade schema.

    The extension is left installed. Dropping it would take every other
    trigram index in the database with it, and this revision is not the only
    possible reason it is there.
    """
    op.drop_index(
        "ix_catalog_products_name_normalized_trgm",
        table_name="catalog_products",
    )
    op.drop_index(
        "ix_catalog_products_sku_normalized_trgm",
        table_name="catalog_products",
    )
    op.drop_index(
        "ix_catalog_products_search_vector",
        table_name="catalog_products",
    )
