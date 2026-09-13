from typing import final, override

from sqlalchemy import RowMapping

from goldy.application.common.ports.catalog import ResolvedPriceType
from goldy.application.error import UnsupportedPriceTypeError
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.money import Money
from goldy.infrastructure.mappers.pricing_row_mapper import PricingRowMapper


@final
class SqlAlchemyPricingRowMapper(PricingRowMapper):
    """Turns a priced row of the projection into the values an order line keeps.

    By hand rather than with adaptix, like every row mapper here: a
    ``RowMapping`` carries no field types for a converter to introspect, and
    the unit is two columns that become one value.

    Only rows that carry a price are handed to :meth:`to_priced_product` — the
    reader keeps the unpriced ones apart — so ``amount`` is never ``None`` here
    and a row without one is a defect of the query, not a product.
    """

    @override
    def to_priced_product(self, row: RowMapping) -> PricedProduct:
        """Builds the snapshot values, refusing what the domain refuses.

        Raises:
            DomainFieldError: an empty name, an article that is not one, a
                price that cannot be money.
            UnsupportedPriceTypeError: the price is in a currency this shop
                cannot price in. The import marks such price types
                unsupported and the resolver refuses them earlier, so reaching
                this means the projection disagrees with itself — still a
                refusal, never a silent substitution of a currency we do like.
        """
        currency_code: str = row["currency"]

        try:
            currency = Currency(currency_code.strip().lower())
        except ValueError as error:
            msg = f"Currency '{currency_code}' is not one this shop prices in."
            raise UnsupportedPriceTypeError(msg) from error

        return PricedProduct(
            product_id=ProductId(value=row["product_id"]),
            sku=Sku(value=row["sku"]),
            name=ProductName(value=row["name"]),
            unit=UnitOfMeasure(row["unit_id"], row["unit_name"]),
            unit_price=Money(row["amount"], currency),
        )

    @override
    def to_resolved_price_type(self, row: RowMapping) -> ResolvedPriceType:
        return ResolvedPriceType(
            price_type_id=PriceTypeId(value=row["price_type_id"]),
            is_supported=row["is_supported"],
        )
