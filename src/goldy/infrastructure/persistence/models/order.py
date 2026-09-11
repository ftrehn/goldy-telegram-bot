from typing import Final

from sqlalchemy import (
    UUID as SA_UUID,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
)
from sqlalchemy.orm import composite, relationship

from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.values.money import Money
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.values.recipient import Recipient
from goldy.infrastructure.persistence.models.base import mapper_registry
from goldy.infrastructure.persistence.models.types import (
    MAX_SOURCE_ID_COLUMN_LENGTH,
    MAX_UNIT_NAME_COLUMN_LENGTH,
    MONEY_COLUMN_PRECISION,
    MONEY_COLUMN_SCALE,
    CancellationInitiatorType,
    CancellationReasonType,
    CurrencyType,
    DeliveryAddressType,
    OrderCommentType,
    OrderNumberType,
    OrderStatusType,
    PhoneNumberType,
    ProductNameType,
    QuantityType,
    SkuType,
    SourceIdType,
)
from goldy.infrastructure.persistence.models.user import MAX_NAME_COLUMN_LENGTH

PAYMENT_COLUMNS: Final[tuple[str, ...]] = (
    "payment_confirmed_at",
    "payment_confirmed_by",
)
"""Columns the schema carries and the mapping deliberately does not.

The owner's decision that there is no payment in the bot stands: there is no
``PAID`` status, no domain method and no command that writes these. They are
created empty all the same, because the question "does a manager need a paid
flag" had "until the orders table is first migrated" as its deadline, and that
migration is the one being written. A nullable column costs nothing now and an
``ALTER`` over a live orders table costs plenty later.

Excluded from the mapper rather than merely unused, so that no attribute
appears on :class:`Order` that reads like domain state nobody maintains.
"""

orders_table: Final[Table] = Table(
    "orders",
    mapper_registry.metadata,
    Column("id", SA_UUID(as_uuid=True), primary_key=True),
    Column("number", OrderNumberType, nullable=False, unique=True),
    Column(
        "customer_id",
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("status", OrderStatusType, nullable=False, index=True),
    Column("price_type_id", SourceIdType(PriceTypeId), nullable=False),
    Column("delivery_address", DeliveryAddressType, nullable=False),
    Column("comment", OrderCommentType, nullable=True),
    Column("recipient_first_name", String(MAX_NAME_COLUMN_LENGTH), nullable=False),
    Column("recipient_last_name", String(MAX_NAME_COLUMN_LENGTH), nullable=True),
    Column("recipient_phone", PhoneNumberType, nullable=False),
    Column("cancelled_by", CancellationInitiatorType, nullable=True),
    Column("cancellation_reason", CancellationReasonType, nullable=True),
    Column("payment_confirmed_at", DateTime(timezone=True), nullable=True),
    Column("payment_confirmed_by", SA_UUID(as_uuid=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
"""One order, as the customer committed to it.

``customer_id`` is the one foreign key an order has, and it restricts rather
than cascades: the order points at a person of ours, and a person with orders
must not be deletable. There is no key into ``catalog_products`` from the
lines — ADR-0003 — because a line is a snapshot and has to outlive the product.

The three ``recipient_*`` columns are in the field order of ``Recipient`` and
must stay in it. A composite is rebuilt positionally, so swapping two of them
swaps the values with nothing failing until somebody reads a delivery note.

There is no total column. :attr:`Order.total` is derived from the lines every
time it is asked for, and the lines of a placed order never change; a stored
total is a second statement of the same fact that can disagree with the first.

No status for payment and none for "exported to 1C" either: settlement happens
outside the bot, and whether the order has reached 1C is the state of an
integration the outbox already tracks.
"""

order_items_table: Final[Table] = Table(
    "order_items",
    mapper_registry.metadata,
    Column(
        "order_id",
        SA_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("position", Integer, primary_key=True, autoincrement=False),
    Column("product_id", SourceIdType(ProductId), nullable=False),
    Column("sku", SkuType, nullable=True),
    Column("name", ProductNameType, nullable=False),
    Column("unit_id", String(MAX_SOURCE_ID_COLUMN_LENGTH), nullable=True),
    Column("unit_name", String(MAX_UNIT_NAME_COLUMN_LENGTH), nullable=False),
    Column(
        "unit_price_amount",
        Numeric(MONEY_COLUMN_PRECISION, MONEY_COLUMN_SCALE),
        nullable=False,
    ),
    Column("unit_price_currency", CurrencyType, nullable=False),
    Column("quantity", QuantityType, nullable=False),
    CheckConstraint("unit_price_amount >= 0", name="unit_price_amount_non_negative"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
)
"""One product as it was at the moment the order was placed.

Keyed by ``(order_id, position)`` and not by ``(order_id, product_id)``: the
line number is what the tabular part of a 1C document is addressed by, and
keying by product would forbid the same item twice in one order — a restriction
that is right for a cart and gets in a manager's way here. ``position`` counts
from 1 and is assigned by ``CheckoutService``, so ``autoincrement`` is off: an
integer primary key column would otherwise be handed a sequence it must not
have.

Every displayed field is a copy rather than a reference. ``product_id`` stays on
the line so a customer can repeat an order and a future export can point at the
right item, but nothing shown is read through it.

``sku`` is nullable because the article is optional in 1C and a strict one here
would refuse to place an order for a product the shop sells perfectly well.

``unit_id`` and ``unit_name`` are the two fields of ``UnitOfMeasure``, in that
order, and ``unit_price_amount`` with ``unit_price_currency`` are the two of
``Money``. Both are composites and both are rebuilt positionally.
"""


def map_orders_table() -> None:
    """Maps the Order aggregate and its snapshot lines.

    ``events_collection`` is absent on purpose — it is not a column, SQLAlchemy
    leaves it unset on a loaded instance, and the command gateway injects the
    request-scoped one on every read. Unlike the cart, an order genuinely
    records events, so a missing collection here would fail on the first
    confirmation rather than eventually.

    Composite column order is the field order of ``Recipient``,
    ``UnitOfMeasure`` and ``Money``. Composites are rebuilt positionally, so
    reordering the arguments below swaps values silently.

    ``order_id`` is mapped onto ``OrderLine`` automatically: it is part of the
    line's identity, not part of what the domain asks about a line.
    """
    mapper_registry.map_imperatively(
        OrderLine,
        order_items_table,
        properties={
            "position": order_items_table.c.position,
            "product_id": order_items_table.c.product_id,
            "sku": order_items_table.c.sku,
            "name": order_items_table.c.name,
            "unit": composite(
                UnitOfMeasure,
                order_items_table.c.unit_id,
                order_items_table.c.unit_name,
            ),
            "unit_price": composite(
                Money,
                order_items_table.c.unit_price_amount,
                order_items_table.c.unit_price_currency,
            ),
            "quantity": order_items_table.c.quantity,
        },
    )

    mapper_registry.map_imperatively(
        Order,
        orders_table,
        properties={
            "id": orders_table.c.id,
            "number": orders_table.c.number,
            "customer_id": orders_table.c.customer_id,
            "status": orders_table.c.status,
            "price_type_id": orders_table.c.price_type_id,
            "delivery_address": orders_table.c.delivery_address,
            "comment": orders_table.c.comment,
            "recipient": composite(
                Recipient,
                orders_table.c.recipient_first_name,
                orders_table.c.recipient_last_name,
                orders_table.c.recipient_phone,
            ),
            "cancelled_by": orders_table.c.cancelled_by,
            "cancellation_reason": orders_table.c.cancellation_reason,
            "created_at": orders_table.c.created_at,
            "updated_at": orders_table.c.updated_at,
            "lines": relationship(
                OrderLine,
                lazy="selectin",
                cascade="all, delete-orphan",
                order_by=order_items_table.c.position,
            ),
        },
        exclude_properties=PAYMENT_COLUMNS,
    )
