from dataclasses import dataclass
from typing import override

from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.value_object import ValueObject
from goldy.domain.common.values.money import Money


@dataclass(frozen=True, kw_only=True)
class PricedProduct(ValueObject):
    """A product with the price this particular customer pays for it.

    Never persisted. It is what the pricing reader assembles out of the
    projection for one checkout, and it is the shape an order line is
    snapshotted from: every field is a validated domain value, so nothing
    reaches an order that the catalog could not vouch for.

    ``sku`` is mandatory, and so is ``unit_price``. A product the projection
    holds without a price under this price list is not a priced product at
    all — the reader reports it separately and the application refuses the
    checkout — and a product without an article is a broken export, which the
    exchange contract rules out by sending the 1C code where the article is
    blank.
    """

    product_id: ProductId
    sku: Sku
    name: ProductName
    unit: UnitOfMeasure
    unit_price: Money

    @override
    def _validate(self) -> None:
        """Every field is already constrained by its own type."""
