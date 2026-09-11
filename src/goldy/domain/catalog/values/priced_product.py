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

    Never persisted. It is what the pricing application service assembles from
    the read model it has just queried, and it is the one place where
    primitives out of that read model become validated domain values before an
    order is allowed to keep them as a snapshot.

    ``sku`` is optional, and that is a fact about the source rather than a
    concession: the article is an optional attribute in 1C and products without
    one exist in practically every database. A mandatory ``Sku`` here would not
    break the import — the projection is Core-only and builds no values — it
    would break ``CheckoutService._build_line``, which is the customer's
    "place order" button. ``Sku`` itself stays strict: it validates the value,
    not its presence.
    """

    product_id: ProductId
    sku: Sku | None
    name: ProductName
    unit: UnitOfMeasure
    unit_price: Money

    @override
    def _validate(self) -> None:
        """Every field is already constrained by its own type."""
