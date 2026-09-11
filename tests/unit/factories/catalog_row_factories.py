"""Builders for the projection rows the catalog read model is assembled from.

A ``RowMapping`` is a mapping and nothing more, so a dictionary standing in for
one lets the row mapper be exercised without a database. What the dictionary
must get right is the *shape*, and for the catalog that shape is deliberately
flat: the projection is Core-only and carries no type decorators, so a real row
hands back the primitives 1C sent rather than value objects. Filling in a
``Sku`` here would prove the mapper works against a row nobody will ever give
it — the opposite mistake to the one ``order_row_factories`` avoids.

The labelled keys are the contract between the gateways and the mapper:
``stock`` is a sum over warehouses rather than a column, ``category_name`` is
labelled because the plain name would collide with the product's own ``name``,
and ``product_id`` says which id a priced row is about.

Products and groups are numbered the way ``catalog_factories`` numbers them, so
a test that prices product 7 there and reads product 7 back here is talking
about one product in both halves.
"""

from decimal import Decimal
from typing import cast

from sqlalchemy import RowMapping

from goldy.domain.common.values.currency import Currency
from tests.unit.factories.catalog_factories import (
    make_category_id,
    make_product_id_value,
)
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    UNIT_NAME,
    UNIT_PRICE,
    UNIT_SOURCE_ID,
)


def make_category_projection_row(
    index: int = 1,
    parent_index: int | None = None,
) -> RowMapping:
    """One row of a category level, with the path the import computed."""
    own = make_category_id(index)
    parent = None if parent_index is None else make_category_id(parent_index)
    path = own if parent is None else f"{parent}/{own}"

    return cast(
        "RowMapping",
        {
            "id": own,
            "parent_id": parent,
            "name": f"Group {index}",
            "path": path,
            "depth": path.count("/"),
        },
    )


def make_listing_row(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    stock: str | None = "10",
) -> RowMapping:
    """One row of a listing or of a page of search results.

    ``price=None`` is what the outer join against the prices returns for a
    product this customer's price type does not price, which is the ordinary
    case rather than a broken one.
    """
    return cast(
        "RowMapping",
        {
            "id": make_product_id_value(index),
            "sku": f"SKU-{index}",
            "name": f"Product {index}",
            "unit_name": UNIT_NAME,
            "amount": None if price is None else Decimal(price),
            "currency": None if price is None else Currency.RUB.value,
            "stock": None if stock is None else Decimal(stock),
        },
    )


def make_product_card_row(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    stock: str | None = "10",
    category_index: int | None = 1,
    description: str | None = None,
    *,
    is_active: bool = True,
) -> RowMapping:
    """One row of the product card query, joined to its group and its price."""
    return cast(
        "RowMapping",
        {
            "id": make_product_id_value(index),
            "sku": f"SKU-{index}",
            "name": f"Product {index}",
            "full_name": f"Product {index}, full name",
            "category_id": (
                None if category_index is None else make_category_id(category_index)
            ),
            "category_name": (
                None if category_index is None else f"Group {category_index}"
            ),
            "unit_name": UNIT_NAME,
            "unit_ratio": Decimal(1),
            "description": description,
            "image_url": None,
            "amount": None if price is None else Decimal(price),
            "currency": None if price is None else Currency.RUB.value,
            "stock": None if stock is None else Decimal(stock),
            "is_active": is_active,
        },
    )


def make_priced_product_row(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    currency: Currency = Currency.RUB,
    *,
    with_sku: bool = True,
) -> RowMapping:
    """One row of the pricing query, on its way to becoming an order line."""
    return cast(
        "RowMapping",
        {
            "product_id": make_product_id_value(index),
            "sku": f"SKU-{index}" if with_sku else None,
            "name": f"Product {index}",
            "unit_id": UNIT_SOURCE_ID,
            "unit_name": UNIT_NAME,
            "amount": None if price is None else Decimal(price),
            "currency": None if price is None else currency.value,
        },
    )


def make_price_type_projection_row(
    price_type_id: str = PRICE_TYPE_ID,
    *,
    is_supported: bool = True,
) -> RowMapping:
    """One row of the price type lookup, already resolved to one list."""
    return cast(
        "RowMapping",
        {"price_type_id": price_type_id, "is_supported": is_supported},
    )
