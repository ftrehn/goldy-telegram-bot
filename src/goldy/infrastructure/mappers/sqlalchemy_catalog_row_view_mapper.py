from typing import final, override

from sqlalchemy import RowMapping

from goldy.application.common.views.catalog import (
    CategoryView,
    PriceTypeView,
    PricedProductView,
    ProductListItemView,
    ProductView,
)
from goldy.application.common.views.money import MoneyView
from goldy.infrastructure.mappers.catalog_row_view_mapper import CatalogRowViewMapper


@final
class SqlAlchemyCatalogRowViewMapper(CatalogRowViewMapper):
    """Flattens projection rows into the views the storefront renders.

    Written by hand rather than with adaptix, for the reason
    ``SqlAlchemyUserRowViewMapper`` gives: a ``RowMapping`` carries no field
    types for a converter to introspect, and half of what these views hold is
    not a column of the product row at all — the price comes from an outer
    join, the stock from a sum over warehouses.

    A missing amount is what "price on request" is made of, and it is turned
    into ``None`` rather than into a zero here, once, so that no screen has to
    decide what an unpriced product costs. A zero would be rendered as free.
    """

    @override
    def to_category_view(self, row: RowMapping) -> CategoryView:
        return CategoryView(
            id=row["id"],
            parent_id=row["parent_id"],
            name=row["name"],
            path=row["path"],
            depth=row["depth"],
        )

    @override
    def to_product_list_item_view(self, row: RowMapping) -> ProductListItemView:
        return ProductListItemView(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            unit_name=row["unit_name"],
            unit_price=_to_money_view(row),
            stock=row["stock"],
        )

    @override
    def to_product_view(self, row: RowMapping) -> ProductView:
        return ProductView(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            full_name=row["full_name"],
            category_id=row["category_id"],
            category_name=row["category_name"],
            unit_name=row["unit_name"],
            unit_ratio=row["unit_ratio"],
            description=row["description"],
            image_url=row["image_url"],
            unit_price=_to_money_view(row),
            stock=row["stock"],
            is_active=row["is_active"],
        )

    @override
    def to_priced_product_view(self, row: RowMapping) -> PricedProductView:
        return PricedProductView(
            product_id=row["product_id"],
            sku=row["sku"],
            name=row["name"],
            unit_id=row["unit_id"],
            unit_name=row["unit_name"],
            unit_price=_to_money_view(row),
        )

    @override
    def to_price_type_view(self, row: RowMapping) -> PriceTypeView:
        return PriceTypeView(
            price_type_id=row["price_type_id"],
            is_supported=row["is_supported"],
        )


def _to_money_view(row: RowMapping) -> MoneyView | None:
    """The price on this row, or nothing when the outer join found none.

    The currency is read from the price row rather than from the price type,
    which is the whole point of duplicating it there: a storefront page would
    otherwise drag a join along for one column.
    """
    amount = row["amount"]

    if amount is None:
        return None

    return MoneyView(amount=amount, currency=row["currency"])
