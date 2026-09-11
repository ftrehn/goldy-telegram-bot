"""Builders for the result rows the order read model is assembled from.

A ``RowMapping`` is a mapping and nothing more, so a dictionary standing in for
one lets the row mappers be exercised without a database. What the dictionary
must get right is the *shape*: the order columns carry type decorators, so a
real row hands back value objects rather than text, and a builder that filled
in bare strings would prove the mapper works against a row nobody will ever
hand it.

Numbered products and the shared constants come from ``shop_factories``, so a
test that prices product 7 there and reads line 7 back here is talking about
one product in both halves.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import RowMapping

from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.cancellation_reason import CancellationReason
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.user_status import UserStatus
from tests.unit.factories.domain_factories import make_phone_number, make_user_id
from tests.unit.factories.shop_factories import (
    ORDER_NUMBER,
    RECIPIENT_FIRST_NAME,
    RECIPIENT_LAST_NAME,
    UNIT_NAME,
    UNIT_PRICE,
    UNIT_SOURCE_ID,
    make_delivery_address,
    make_order_comment,
    make_order_id,
    make_order_number,
    make_price_type_id,
    make_product_id,
)

PLACED_AT: datetime = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
EDITED_AT: datetime = datetime(2026, 3, 1, 13, 0, tzinfo=UTC)


def make_order_row(
    status: OrderStatus = OrderStatus.NEW,
    customer_status: UserStatus = UserStatus.ACTIVE,
    comment: str | None = None,
    cancelled_by: CancellationInitiator | None = None,
    cancellation_reason: str | None = None,
) -> RowMapping:
    """One row of the order card query, joined to the buyer's status."""
    return cast(
        "RowMapping",
        {
            "id": make_order_id(),
            "number": make_order_number(),
            "customer_id": make_user_id(),
            "customer_status": customer_status,
            "status": status,
            "price_type_id": make_price_type_id(),
            "delivery_address": make_delivery_address(),
            "comment": None if comment is None else make_order_comment(comment),
            "recipient_first_name": RECIPIENT_FIRST_NAME,
            "recipient_last_name": RECIPIENT_LAST_NAME,
            "recipient_phone": make_phone_number(),
            "cancelled_by": cancelled_by,
            "cancellation_reason": (
                None
                if cancellation_reason is None
                else CancellationReason(value=cancellation_reason)
            ),
            "created_at": PLACED_AT,
            "updated_at": EDITED_AT,
        },
    )


def make_order_line_row(
    position: int = 1,
    index: int = 1,
    quantity: int = 1,
    price: str = UNIT_PRICE,
    stock: str | None = None,
    *,
    with_sku: bool = True,
) -> RowMapping:
    """One row of the lines query, with today's stock joined onto the snapshot.

    ``stock=None`` is what the join returns for a product the catalog no longer
    holds — the ordinary case for an old order, and the one the card must draw
    without a figure rather than as a zero.
    """
    return cast(
        "RowMapping",
        {
            "order_id": make_order_id(),
            "position": position,
            "product_id": make_product_id(index),
            "sku": Sku(value=f"SKU-{index}") if with_sku else None,
            "name": ProductName(value=f"Товар {index}"),
            "unit_id": UNIT_SOURCE_ID,
            "unit_name": UNIT_NAME,
            "unit_price_amount": Decimal(price),
            "unit_price_currency": Currency.RUB,
            "quantity": Quantity(value=quantity),
            "stock": None if stock is None else Decimal(stock),
        },
    )


def make_order_list_row(
    status: OrderStatus = OrderStatus.NEW,
    customer_status: UserStatus = UserStatus.ACTIVE,
    customer_last_name: str | None = RECIPIENT_LAST_NAME,
    total: str | None = UNIT_PRICE,
    line_count: int = 1,
    number: str = ORDER_NUMBER,
) -> RowMapping:
    """One row of a history page or of the staff queue, totalled in SQL.

    ``total=None`` is what the outer join gives an order with no lines at all.
    The domain does not produce one, and the row is built anyway because the
    queue drawing nothing at all is worse than the queue drawing a zero.
    """
    return cast(
        "RowMapping",
        {
            "id": make_order_id(),
            "number": make_order_number(number),
            "customer_id": make_user_id(),
            "customer_first_name": RECIPIENT_FIRST_NAME,
            "customer_last_name": customer_last_name,
            "customer_status": customer_status,
            "status": status,
            "total_amount": None if total is None else Decimal(total),
            "total_currency": None if total is None else Currency.RUB.value,
            "line_count": line_count,
            "created_at": PLACED_AT,
        },
    )
