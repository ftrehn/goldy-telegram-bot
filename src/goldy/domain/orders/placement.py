from dataclasses import dataclass
from typing import final

from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.recipient import Recipient
from goldy.domain.users.values.user_id import UserId


@final
@dataclass(frozen=True, kw_only=True)
class Placement:
    """Everything ``Order.place`` needs, bundled the way ``Registration`` is.

    A parameter object because ``PLR0913`` counts keyword-only arguments too,
    and because these six always travel together.

    Deliberately not the same object as ``Checkout``, even though one is built
    from the other. The use case is holding a cart and a price list; the
    aggregate needs finished lines. Handing ``Order.place`` a ``Checkout``
    would hand it a ``Cart``, and the order would start depending on the cart
    for no reason at all.

    Not a value object: it carries mutable ``OrderLine`` entities, and nothing
    compares two placements.
    """

    customer_id: UserId
    lines: tuple[OrderLine, ...]
    delivery_address: DeliveryAddress
    recipient: Recipient
    comment: OrderComment | None
    price_type_id: PriceTypeId
