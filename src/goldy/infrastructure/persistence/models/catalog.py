"""The catalog projection: six tables and not one mapped class.

The catalog is a read model of 1C — see ADR-0002 — so nothing here is mapped
imperatively onto anything. Imperative mapping earns its keep where an object
has behaviour and a life cycle, and a projection has neither: it is overwritten,
never edited by a business rule. Leaving it Core-only also keeps
``setup_map_tables()`` small, and stops a class appearing that somebody would
reasonably mistake for a catalog domain model that ADR-0002 forbids.

Core-only does not make importing this module optional. The metadata is what
alembic diffs against, and a table nobody imported is a table alembic reports
no difference for while the database has none of it.

There is not one foreign key inside the projection, and none from
``order_items`` into ``catalog_products`` either. Both ADRs say why: rows arrive
out of order over RabbitMQ, so a key would reject a price whose product has not
landed yet, and an order line is a snapshot that must survive the product being
withdrawn.

Prices and stock are separate narrow tables rather than columns on the card,
because they change an order of magnitude more often. Updating a stock figure
held on the product row would rewrite that row's GIN indexes too, which is a
search index rebuild for a number nobody searches by.
"""

from typing import Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    Index,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR

from goldy.infrastructure.persistence.models.base import mapper_registry
from goldy.infrastructure.persistence.models.catalog_search import (
    NAME_NORMALIZED_SQL,
    SEARCH_VECTOR_SQL,
    SKU_NORMALIZED_SQL,
)
from goldy.infrastructure.persistence.models.types import (
    MAX_CURRENCY_COLUMN_LENGTH,
    MAX_PHONE_NUMBER_COLUMN_LENGTH,
    MAX_PRODUCT_NAME_COLUMN_LENGTH,
    MAX_SKU_COLUMN_LENGTH,
    MAX_SOURCE_ID_COLUMN_LENGTH,
    MAX_UNIT_NAME_COLUMN_LENGTH,
    MEASURE_COLUMN_PRECISION,
    MEASURE_COLUMN_SCALE,
    MONEY_COLUMN_PRECISION,
    MONEY_COLUMN_SCALE,
)

MAX_CATEGORY_PATH_LENGTH: Final[int] = 1024
MAX_BATCH_ID_LENGTH: Final[int] = 64

catalog_categories_table: Final[Table] = Table(
    "catalog_categories",
    mapper_registry.metadata,
    Column("id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column("parent_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), nullable=True, index=True),
    Column("name", String(MAX_PRODUCT_NAME_COLUMN_LENGTH), nullable=False),
    Column("path", String(MAX_CATEGORY_PATH_LENGTH), nullable=False, index=True),
    Column("depth", SmallInteger, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)
"""One section of the 1C nomenclature reference.

``path`` and ``depth`` are denormalised, and that is the whole reason the
storefront works. Products in 1C sit in the leaves of the hierarchy, so a
listing selected by ``parent_id`` shows an empty group wherever that group has
subgroups; selecting a whole subtree is ``path LIKE :prefix || '%'`` over an
ordinary btree index, and deactivating a subtree uses the same mask, so no
active subgroup is ever left under a deactivated parent.

A recursive CTE would do the same without the column, but it requires every
parent to have arrived already, and RabbitMQ does not order messages. The price
of the denormalisation is a clause of the exchange contract: the category
snapshot is always complete and always one message. Products keep arriving in
batches.
"""

catalog_products_table: Final[Table] = Table(
    "catalog_products",
    mapper_registry.metadata,
    Column("id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column("sku", String(MAX_SKU_COLUMN_LENGTH), nullable=True),
    Column("name", String(MAX_PRODUCT_NAME_COLUMN_LENGTH), nullable=False),
    Column("full_name", Text, nullable=True),
    Column(
        "category_id",
        String(MAX_SOURCE_ID_COLUMN_LENGTH),
        nullable=True,
        index=True,
    ),
    Column("unit_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), nullable=True),
    Column("unit_name", String(MAX_UNIT_NAME_COLUMN_LENGTH), nullable=False),
    Column(
        "unit_ratio",
        Numeric(MEASURE_COLUMN_PRECISION, MEASURE_COLUMN_SCALE),
        nullable=False,
        server_default="1",
    ),
    Column("description", Text, nullable=True),
    Column("image_url", Text, nullable=True),
    Column("is_active", Boolean, nullable=False),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
    Column(
        "sku_normalized",
        String(MAX_SKU_COLUMN_LENGTH),
        Computed(SKU_NORMALIZED_SQL, persisted=True),
        nullable=True,
    ),
    Column(
        "name_normalized",
        String(MAX_PRODUCT_NAME_COLUMN_LENGTH),
        Computed(NAME_NORMALIZED_SQL, persisted=True),
        nullable=False,
    ),
    Column(
        "search_vector",
        TSVECTOR,
        Computed(SEARCH_VECTOR_SQL, persisted=True),
        nullable=False,
    ),
)
"""One product of the 1C nomenclature reference.

Groups never arrive here — an element of the reference that is a group goes to
``catalog_categories``, an element that is a product goes here. That is a
clause of the exchange contract rather than a flag on a row, which is why there
is no column for it.

``sku`` is nullable because the article is an optional attribute in 1C, and a
product without one is ordinary. Search by article does not suffer: the
generated ``sku_normalized`` is NULL for such a row and never enters the index.

A product is deactivated and kept forever rather than deleted. Placed orders
point at it and a customer expects to open the card of something they bought
last spring.

The three generated columns are what search reads; the rules behind them live
in ``catalog_search`` next to their Python mirrors.
"""

catalog_price_types_table: Final[Table] = Table(
    "catalog_price_types",
    mapper_registry.metadata,
    Column("id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column("name", String(MAX_PRODUCT_NAME_COLUMN_LENGTH), nullable=False),
    Column("currency", String(MAX_CURRENCY_COLUMN_LENGTH), nullable=False),
    Column("is_supported", Boolean, nullable=False),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)
"""One price list, as 1C names and denominates it.

``is_supported`` is false when the currency 1C sent is not one this service
knows. The row is kept rather than dropped, and its prices are refused, so a
customer bound to that list gets a plain "ask a manager" instead of somebody
else's roubles — a silent fall back to the default list is exactly the failure
this column exists to prevent.
"""

catalog_prices_table: Final[Table] = Table(
    "catalog_prices",
    mapper_registry.metadata,
    Column("product_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column(
        "price_type_id",
        String(MAX_SOURCE_ID_COLUMN_LENGTH),
        primary_key=True,
        index=True,
    ),
    Column("amount", Numeric(MONEY_COLUMN_PRECISION, MONEY_COLUMN_SCALE), nullable=False),
    Column("currency", String(MAX_CURRENCY_COLUMN_LENGTH), nullable=False),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("amount >= 0", name="amount_non_negative"),
)
"""What one product costs under one price list.

The currency is duplicated here although the price list carries it too. That is
deliberate: without it every storefront page would drag a join along for one
column, and the currency of a price list changes approximately never — and when
it does, it changes through the same import that writes both rows.

Rows are deleted on a sweep rather than deactivated, unlike products. A price
withdrawn in 1C that stays in the projection is a price the shop does not
offer, which is money lost directly. The sweep is confined to the scope of the
batch, or exporting one price list would wipe every other.

The check is named because the naming convention includes
``%(constraint_name)s`` and an anonymous check breaks DDL generation outright.
"""

catalog_stock_table: Final[Table] = Table(
    "catalog_stock",
    mapper_registry.metadata,
    Column("product_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column("warehouse_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), primary_key=True),
    Column(
        "quantity",
        Numeric(MEASURE_COLUMN_PRECISION, MEASURE_COLUMN_SCALE),
        nullable=False,
    ),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("quantity >= 0", name="quantity_non_negative"),
)
"""How much of one product is free to sell at one warehouse.

Keyed by ``(product_id, warehouse_id)`` from the first day although 1C gives no
warehouse breakdown yet — until it does, the consumer writes a fixed ``'*'``.
The storefront query sums with a group-by from the first day for the same
reason, so real warehouses appearing changes neither the SQL nor the gateway
signature.

``quantity`` is fractional because stock is only ever displayed, never
multiplied: metres and kilograms print fine and reach no arithmetic. It is the
**free** remainder as computed by 1C; on hand and reserved are not stored
separately and will not be, which would be two columns and a second question
the bot cannot answer.
"""

catalog_price_type_bindings_table: Final[Table] = Table(
    "catalog_price_type_bindings",
    mapper_registry.metadata,
    Column("phone_number", String(MAX_PHONE_NUMBER_COLUMN_LENGTH), primary_key=True),
    Column("price_type_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), nullable=False),
    Column("source_counterparty_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), nullable=True),
    Column("batch_id", String(MAX_BATCH_ID_LENGTH), nullable=False),
    Column("source_changed_at", DateTime(timezone=True), nullable=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)
"""Which price list a person buys at, keyed by their phone number.

Not by ``user_id``, and there is no foreign key to ``users``. In 1C the price
list belongs to a counterparty, and a counterparty may not have registered in
the bot at all: a row keyed by user id would have nowhere to go, the message
would be dropped, and after registering that customer would silently get
default prices forever, because nobody re-sends bindings. Keyed by number the
row simply waits, and the pricing gateway joins ``users.phone_number`` in the
one query it already makes.

``synced_at`` and ``batch_id`` rather than ``assigned_at``: a binding withdrawn
in 1C is swept like the rest of the projection. Recording when it was assigned
instead would leave the customer on an old price list forever.

``source_counterparty_id`` exists so the consumer need not resolve the
counterparty again on every message. It reaches no query and no domain object —
there is no counterparty in this domain, literally — which is also why the
table is named after the binding and not after the counterparty.
"""

catalog_products_search_vector_index: Final[Index] = Index(
    "ix_catalog_products_search_vector",
    catalog_products_table.c.search_vector,
    postgresql_using="gin",
    postgresql_where=catalog_products_table.c.is_active,
)
"""Morphology of the name: "дрели" finds "дрель", which only a dictionary does."""

catalog_products_sku_trigram_index: Final[Index] = Index(
    "ix_catalog_products_sku_normalized_trgm",
    catalog_products_table.c.sku_normalized,
    postgresql_using="gin",
    postgresql_ops={"sku_normalized": "gin_trgm_ops"},
    postgresql_where=catalog_products_table.c.is_active,
)
"""A fragment of an article — "123" inside "AB-12345" — which no dictionary does."""

catalog_products_name_trigram_index: Final[Index] = Index(
    "ix_catalog_products_name_normalized_trgm",
    catalog_products_table.c.name_normalized,
    postgresql_using="gin",
    postgresql_ops={"name_normalized": "gin_trgm_ops"},
    postgresql_where=catalog_products_table.c.is_active,
)
"""Tolerance of typos in the name, where the dictionary finds nothing at all.

All three indexes are partial on ``is_active`` — a deactivated product is never
searched for — which is what keeps three GIN indexes on one table cheap. They
need ``pg_trgm``, so the migration that creates them is separate from the one
that creates the schema: a managed database that refuses the extension then
fails one revision with an obvious cause, leaves the schema applied, and
degrades search to ``ILIKE`` until somebody grants it.
"""
