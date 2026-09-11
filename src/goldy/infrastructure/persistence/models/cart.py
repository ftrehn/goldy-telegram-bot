from typing import Final

from sqlalchemy import (
    UUID as SA_UUID,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Table,
)
from sqlalchemy.orm import relationship

from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.entities.cart_line import CartLine
from goldy.domain.catalog.values.product_id import ProductId
from goldy.infrastructure.persistence.models.base import mapper_registry
from goldy.infrastructure.persistence.models.types import QuantityType, SourceIdType

carts_table: Final[Table] = Table(
    "carts",
    mapper_registry.metadata,
    Column("id", SA_UUID(as_uuid=True), primary_key=True),
    Column(
        "user_id",
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
"""One draft order per person, whichever platform they are writing from.

The key is a surrogate ``CartId`` with ``user_id`` beside it rather than the
user id itself, because keying one aggregate by another welds their life cycles
together. "One cart per person" therefore spans aggregates, and rules that span
aggregates are held here: ``unique (user_id)`` is what makes two simultaneous
first additions land on one row, where a read-before-write would lose the race.
That index is also what ``ensure_for`` relies on — ``INSERT ... ON CONFLICT
(user_id) DO NOTHING`` needs it to exist.

There is no status column and there will not be one. A cart that has been
checked out is simply empty again, so no "ordered cart" state exists for
somebody to render one day as though it were still a draft.
"""

cart_items_table: Final[Table] = Table(
    "cart_items",
    mapper_registry.metadata,
    Column(
        "cart_id",
        SA_UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("product_id", SourceIdType(ProductId), primary_key=True),
    Column("quantity", QuantityType, nullable=False),
    Column("added_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("quantity > 0", name="quantity_positive"),
)
"""One product and how many of it, keyed by ``(cart_id, product_id)``.

That key is "one product, one line" as a fact of the schema rather than a check
the aggregate has to remember: adding the same product again raises the
quantity, and nothing can produce a second row for it.

No price column. The price belongs to the projection and moves without us while
a cart lives for days, so it is joined on every render — which is what makes a
new price list reprice an existing cart at once instead of leaving stale
numbers in it.

The check restates ``Quantity``'s "at least one": zero does not exist in the
domain, removing a line is ``remove_item``, and a hand-written zero here would
only surface as a refusal to build the value object on some later load.
"""


def map_carts_table() -> None:
    """Maps the Cart aggregate and the lines inside it.

    ``events_collection`` is deliberately absent, as it is for ``User``. It is
    not a column, so SQLAlchemy leaves it unset on a loaded instance and the
    command gateway supplies the request-scoped one on every read. The cart
    records no events today, which makes the omission look harmless — it is
    not: the first method somebody makes event-recording would fail on a
    missing attribute, far from the load that caused it.

    ``cart_id`` is mapped onto ``CartLine`` automatically, the way ``user_id``
    is onto ``MessengerAccount``: it is part of the line's identity and not
    part of what the domain asks about a line.
    """
    mapper_registry.map_imperatively(
        CartLine,
        cart_items_table,
        properties={
            "product_id": cart_items_table.c.product_id,
            "quantity": cart_items_table.c.quantity,
            "added_at": cart_items_table.c.added_at,
        },
    )

    mapper_registry.map_imperatively(
        Cart,
        carts_table,
        properties={
            "id": carts_table.c.id,
            "user_id": carts_table.c.user_id,
            "created_at": carts_table.c.created_at,
            "updated_at": carts_table.c.updated_at,
            "lines": relationship(
                CartLine,
                lazy="selectin",
                cascade="all, delete-orphan",
                order_by=cart_items_table.c.added_at,
            ),
        },
    )
