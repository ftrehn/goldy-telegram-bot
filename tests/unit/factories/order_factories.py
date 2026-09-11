"""Builders for what crosses the application layer on the order side.

Separate from ``shop_factories`` for the reason ``catalog_factories`` is: none
of this is a domain value. A priced product view is what the pricing read model
hands over before anything has been validated, and an order view is what a card
looks like once a row mapper has been over it — neither is ever an aggregate.

Products are numbered exactly as they are in the domain builders, so a test
that puts product 7 in a cart and prices product 7 here is talking about one
product in both halves.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from goldy.application.common.views.catalog import PricedProductView
from goldy.application.common.views.money import MoneyView
from goldy.application.common.views.order import (
    OrderLineView,
    OrderListItemView,
    OrderView,
)
from goldy.domain.common.values.currency import Currency
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.user_id import UserId
from tests.unit.factories.catalog_factories import (
    make_money_view,
    make_product_id_value,
)
from tests.unit.factories.domain_factories import CUSTOMER_PHONE, make_user_id
from tests.unit.factories.shop_factories import (
    DELIVERY_ADDRESS,
    ORDER_ID,
    ORDER_NUMBER,
    PRICE_TYPE_ID,
    RECIPIENT_FIRST_NAME,
    RECIPIENT_LAST_NAME,
    UNIT_NAME,
    UNIT_PRICE,
)

PLACED_AT: datetime = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def make_priced_product_view(
    index: int = 1,
    price: str | None = UNIT_PRICE,
    currency: Currency = Currency.RUB,
    *,
    with_sku: bool = True,
) -> PricedProductView:
    """One row of the pricing read model.

    ``price=None`` is how a test asks for a product the storefront shows as
    "price on request": present in the catalog, impossible to order.
    """
    return PricedProductView(
        product_id=make_product_id_value(index),
        sku=f"SKU-{index}" if with_sku else None,
        name=f"Товар {index}",
        unit_id="1c-unit-796",
        unit_name=UNIT_NAME,
        unit_price=None if price is None else make_money_view(price, currency),
    )


def make_order_line_view(
    position: int = 1,
    index: int = 1,
    quantity: int = 1,
    price: str = UNIT_PRICE,
) -> OrderLineView:
    unit_price = make_money_view(price)

    return OrderLineView(
        position=position,
        product_id=make_product_id_value(index),
        sku=f"SKU-{index}",
        name=f"Товар {index}",
        unit_name=UNIT_NAME,
        quantity=quantity,
        unit_price=unit_price,
        line_total=MoneyView(
            amount=unit_price.amount * quantity,
            currency=unit_price.currency,
        ),
        stock=None,
    )


def make_order_view(
    customer_id: UserId | None = None,
    status: OrderStatus = OrderStatus.NEW,
    order_id: str = ORDER_ID,
    lines: tuple[OrderLineView, ...] | None = None,
    *,
    is_cancellable: bool = True,
    is_editable: bool = True,
    is_terminal: bool = False,
) -> OrderView:
    """A card as the row mapper would have built it.

    The three flags are handed in rather than derived, because deriving them
    here would be a third statement of the cancellation rule — the mapper reads
    the domain constants, and a test that wants an uncancellable card says so.
    """
    order_lines = lines if lines is not None else (make_order_line_view(),)
    total = MoneyView(
        amount=sum(
            (line.line_total.amount for line in order_lines),
            start=Decimal("0.00"),
        ),
        currency=Currency.RUB.value,
    )

    return OrderView(
        id=UUID(order_id),
        number=ORDER_NUMBER,
        customer_id=customer_id if customer_id is not None else make_user_id(),
        customer_is_blocked=False,
        status=status.value,
        price_type_id=PRICE_TYPE_ID,
        delivery_address=DELIVERY_ADDRESS,
        recipient_first_name=RECIPIENT_FIRST_NAME,
        recipient_last_name=RECIPIENT_LAST_NAME,
        recipient_phone_number=CUSTOMER_PHONE,
        comment=None,
        cancelled_by=None,
        cancellation_reason=None,
        lines=order_lines,
        total=total,
        is_cancellable=is_cancellable,
        is_editable=is_editable,
        is_terminal=is_terminal,
        created_at=PLACED_AT,
        updated_at=PLACED_AT,
    )


def make_order_list_item_view(
    customer_id: UserId | None = None,
    number: str = ORDER_NUMBER,
    status: OrderStatus = OrderStatus.NEW,
    order_id: str = ORDER_ID,
) -> OrderListItemView:
    return OrderListItemView(
        id=UUID(order_id),
        number=number,
        customer_id=customer_id if customer_id is not None else make_user_id(),
        customer_name=f"{RECIPIENT_FIRST_NAME} {RECIPIENT_LAST_NAME}",
        customer_is_blocked=False,
        status=status.value,
        total=make_money_view(),
        line_count=1,
        created_at=PLACED_AT,
    )
