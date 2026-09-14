from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import final

from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.quantity import Quantity


@final
@dataclass(eq=False, kw_only=True)
class CartLine:
    """One product and how many of it the person wants.

    Its identity is ``(cart_id, product_id)``, which is also the table's
    primary key, so "one product, one line" holds without the aggregate
    checking for it: adding the same product again raises the quantity.

    Carries no price on purpose. The price is read from the catalog projection
    by the customer's price type every time the cart is shown, which is what
    makes assigning a price type reprice an existing cart at once instead of
    leaving stale numbers behind.

    A mutable dataclass rather than a frozen value object because it is mapped
    imperatively and SQLAlchemy assigns to these attributes when it loads a
    row — the same reason ``MessengerAccount`` is one.
    """

    product_id: ProductId
    quantity: Quantity
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))
