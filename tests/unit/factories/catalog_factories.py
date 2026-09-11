"""Builders for the catalog read models and for the rows an import carries.

Separate from ``shop_factories`` because nothing here is a domain value. The
catalog is a projection: what crosses the application layer are views on one
side and plain rows on the other, and neither is ever validated into anything.

Products are numbered the same way the domain builders number them, so a test
that seeds product 7 into the projection and finds it in a cart is talking
about the same product in both halves.
"""

from datetime import UTC, datetime
from decimal import Decimal

from goldy.application.common.ports.catalog import (
    CatalogScope,
    CatalogScopeKind,
    CatalogSnapshot,
    CategoryRow,
    PriceRow,
    PriceTypeBindingRow,
    PriceTypeRow,
    ProductRow,
    StockRow,
)
from goldy.application.common.views.catalog import (
    CategoryView,
    PriceTypeView,
    ProductListItemView,
    ProductView,
)
from goldy.application.common.views.money import MoneyView
from goldy.domain.common.values.currency import Currency
from tests.unit.factories.shop_factories import (
    PRICE_TYPE_ID,
    PRODUCT_ID_PREFIX,
    UNIT_NAME,
    UNIT_PRICE,
)

BATCH_ID: str = "batch-0001"
CATEGORY_ID_PREFIX: str = "1c-category-"
WAREHOUSE_ID: str = "*"
SOURCE_CHANGED_AT: datetime = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def make_category_id(index: int = 1) -> str:
    return f"{CATEGORY_ID_PREFIX}{index}"


def make_product_id_value(index: int = 1) -> str:
    return f"{PRODUCT_ID_PREFIX}{index}"


def make_money_view(
    amount: str = UNIT_PRICE,
    currency: Currency = Currency.RUB,
) -> MoneyView:
    return MoneyView(amount=Decimal(amount), currency=currency.value)


def make_category_view(
    index: int = 1,
    parent_index: int | None = None,
    name: str | None = None,
) -> CategoryView:
    """A group whose ``path`` is built the way the import would build it."""
    own = make_category_id(index)
    parent = None if parent_index is None else make_category_id(parent_index)
    path = own if parent is None else f"{parent}/{own}"

    return CategoryView(
        id=own,
        parent_id=parent,
        name=name if name is not None else f"Group {index}",
        path=path,
        depth=path.count("/"),
    )


def make_product_list_item(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    stock: str | None = "10",
) -> ProductListItemView:
    return ProductListItemView(
        id=make_product_id_value(index),
        sku=f"SKU-{index}",
        name=f"Product {index}",
        unit_name=UNIT_NAME,
        unit_price=None if price is None else make_money_view(price),
        stock=None if stock is None else Decimal(stock),
    )


def make_product_view(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    stock: str | None = "10",
    category_index: int | None = 1,
    *,
    is_active: bool = True,
) -> ProductView:
    return ProductView(
        id=make_product_id_value(index),
        sku=f"SKU-{index}",
        name=f"Product {index}",
        full_name=None,
        category_id=None if category_index is None else make_category_id(category_index),
        category_name=None if category_index is None else f"Group {category_index}",
        unit_name=UNIT_NAME,
        unit_ratio=Decimal(1),
        description=None,
        image_url=None,
        unit_price=None if price is None else make_money_view(price),
        stock=None if stock is None else Decimal(stock),
        is_active=is_active,
    )


def make_price_type_view(
    price_type_id: str = PRICE_TYPE_ID,
    *,
    is_supported: bool = True,
) -> PriceTypeView:
    return PriceTypeView(price_type_id=price_type_id, is_supported=is_supported)


def make_category_row(index: int = 1, parent_index: int | None = None) -> CategoryRow:
    return CategoryRow(
        id=make_category_id(index),
        parent_id=None if parent_index is None else make_category_id(parent_index),
        name=f"Group {index}",
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_product_row(index: int = 1, category_index: int | None = 1) -> ProductRow:
    return ProductRow(
        id=make_product_id_value(index),
        sku=f"SKU-{index}",
        name=f"Product {index}",
        category_id=None if category_index is None else make_category_id(category_index),
        unit_name=UNIT_NAME,
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_price_type_row(
    price_type_id: str = PRICE_TYPE_ID,
    currency: str = "rub",
) -> PriceTypeRow:
    return PriceTypeRow(
        id=price_type_id,
        name="Wholesale",
        currency=currency,
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_price_row(
    index: int = 1,
    amount: str = UNIT_PRICE,
    currency: str = "rub",
    price_type_id: str = PRICE_TYPE_ID,
) -> PriceRow:
    return PriceRow(
        product_id=make_product_id_value(index),
        price_type_id=price_type_id,
        amount=Decimal(amount),
        currency=currency,
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_stock_row(index: int = 1, quantity: str = "10") -> StockRow:
    return StockRow(
        product_id=make_product_id_value(index),
        warehouse_id=WAREHOUSE_ID,
        quantity=Decimal(quantity),
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_binding_row(
    phone_number: str = "+79991234567",
    price_type_id: str = PRICE_TYPE_ID,
) -> PriceTypeBindingRow:
    return PriceTypeBindingRow(
        phone_number=phone_number,
        price_type_id=price_type_id,
        source_changed_at=SOURCE_CHANGED_AT,
    )


def make_scope(
    kind: CatalogScopeKind = CatalogScopeKind.PRODUCTS,
    price_type_id: str | None = None,
    warehouse_id: str | None = None,
) -> CatalogScope:
    return CatalogScope(
        kind=kind,
        price_type_id=price_type_id,
        warehouse_id=warehouse_id,
    )


def make_snapshot(
    scope: CatalogScope | None = None,
    batch_id: str = BATCH_ID,
    categories: tuple[CategoryRow, ...] = (),
    products: tuple[ProductRow, ...] = (),
    price_types: tuple[PriceTypeRow, ...] = (),
    prices: tuple[PriceRow, ...] = (),
    stock: tuple[StockRow, ...] = (),
    bindings: tuple[PriceTypeBindingRow, ...] = (),
) -> CatalogSnapshot:
    """A batch carrying only what the test named, scoped to products."""
    return CatalogSnapshot(
        batch_id=batch_id,
        scope=scope if scope is not None else make_scope(),
        categories=categories,
        products=products,
        price_types=price_types,
        prices=prices,
        stock=stock,
        price_type_bindings=bindings,
    )
