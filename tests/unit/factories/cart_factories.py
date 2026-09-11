"""Builders for both halves of what the cart gateway deals in.

The joined rows that go in and the views that come out, in one module for the
reason ``catalog_factories`` keeps rows and views together: a test that builds a
row, maps it and then totals the result is one story, and splitting it over two
modules would only make them import each other.

Half of one of these rows is the cart's own and half is the catalog's, and the
halves differ in shape. ``product_id`` and ``quantity`` are columns of
``cart_items`` and carry type decorators, so they arrive as value objects;
everything else comes from the projection, which is Core-only and hands back
plain text and numbers. A builder that flattened both halves would exercise the
mapper against a row nobody will ever give it.

``product=False`` is the row a ``LEFT JOIN`` produces when the projection holds
no such product at all, which is the state the "remove unavailable" button
exists for.
"""

from decimal import Decimal
from typing import cast

from sqlalchemy import RowMapping

from goldy.application.common.views.cart import CartLineView
from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.quantity import Quantity
from tests.unit.factories.catalog_factories import make_product_id_value
from tests.unit.factories.shop_factories import (
    UNIT_NAME,
    UNIT_PRICE,
    make_product_id,
)


def make_cart_line_row(
    index: int = 1,
    quantity: int = 1,
    price: str | None = UNIT_PRICE,
    stock: str | None = None,
    *,
    is_active: bool = True,
    product: bool = True,
) -> RowMapping:
    """One line of the cart, priced at the moment the screen is drawn."""
    return cast(
        "RowMapping",
        {
            "product_id": make_product_id(index),
            "quantity": Quantity(value=quantity),
            "sku": f"SKU-{index}" if product else None,
            "name": f"Product {index}" if product else None,
            "unit_name": UNIT_NAME if product else None,
            "is_active": is_active if product else None,
            "amount": None if price is None else Decimal(price),
            "currency": None if price is None else Currency.RUB.value,
            "stock": None if stock is None else Decimal(stock),
        },
    )


def make_cart_line_view(
    index: int = 1,
    quantity: int = 1,
    price: str | None = UNIT_PRICE,
    currency: Currency = Currency.RUB,
    stock: str | None = None,
    *,
    is_available: bool = True,
) -> CartLineView:
    """One drawn line, already priced or already known to have no price."""
    amount = None if price is None else Decimal(price)
    money = None if amount is None else MoneyView(amount=amount, currency=currency.value)
    line_total = (
        None
        if amount is None
        else MoneyView(amount=amount * quantity, currency=currency.value)
    )

    return CartLineView(
        product_id=make_product_id_value(index),
        sku=f"SKU-{index}",
        name=f"Product {index}",
        unit_name=UNIT_NAME,
        quantity=quantity,
        unit_price=money,
        line_total=line_total,
        stock=None if stock is None else Decimal(stock),
        is_available=is_available,
    )
