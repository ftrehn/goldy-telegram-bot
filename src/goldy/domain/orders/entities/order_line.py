from dataclasses import dataclass
from typing import final

from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.values.money import Money
from goldy.domain.common.values.quantity import Quantity


@final
@dataclass(eq=False, kw_only=True)
class OrderLine:
    """One product as it was at the moment the order was placed.

    A snapshot rather than a reference. The catalog is a projection of 1C and
    will change underneath us — a renamed product, a new price, an article that
    was corrected — while the order has to keep showing what was agreed.
    ``product_id`` stays on the line all the same, but only so the customer can
    repeat an order and so a future export can point at the right item; nothing
    displayed is ever read through it.

    ``sku`` may be missing because the article is an optional attribute in 1C,
    and a strict article here would refuse to place an order for a product the
    shop sells perfectly well. ``unit`` is part of the snapshot for the
    opposite reason: a quantity without its unit means nothing to the customer,
    and looking the unit up in the catalog at display time would undo the
    snapshot.

    Its key is ``(order_id, position)``, not ``(order_id, product_id)``: the
    line number is what the tabular part of a 1C document is addressed by, and
    keying by product would forbid the same item twice in one order — a
    restriction that makes sense in a cart and one day gets in a manager's way
    here.

    ``position`` counts from 1 and is assigned by ``CheckoutService``; the line
    has no ``__post_init__`` of its own, so nothing renumbers behind its back.

    A mutable dataclass because it is mapped imperatively, like every other
    entity here.
    """

    position: int
    product_id: ProductId
    sku: Sku | None
    name: ProductName
    unit: UnitOfMeasure
    unit_price: Money
    quantity: Quantity

    @property
    def total(self) -> Money:
        return self.unit_price.times(self.quantity)
