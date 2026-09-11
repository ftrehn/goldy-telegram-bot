"""Builders for the catalog values, the cart and the order.

One module rather than three, because almost nothing here is built alone: an
order needs lines, a line needs a priced product, and a priced product needs
money. Split by package they would only import each other in a ring around the
same defaults.

Products are numbered instead of named. ``make_product_id(7)`` is the same id
every time and reads as a number in a failure message, which is what lets a
test say "the cart holds products 1 and 2" and mean it. The id itself is a
string shaped the way 1C hands one over, because that is what ``ProductId`` now
is — ``_index_of`` reads the number back out when a helper has a line and needs
to price it.
"""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Final
from uuid import UUID

from goldy.domain.carts.entities.cart import Cart
from goldy.domain.carts.values.cart_id import CartId
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.common.values.currency import Currency
from goldy.domain.common.values.money import Money
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.orders.checkout import Checkout
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.placement import Placement
from goldy.domain.orders.services.authorization.permission import OrderAccessContext
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.delivery_address import DeliveryAddress
from goldy.domain.orders.values.order_comment import OrderComment
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_number import OrderNumber
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.orders.values.recipient import Recipient
from goldy.domain.users.entities.user import User
from goldy.domain.users.values.user_id import UserId
from tests.unit.factories.domain_factories import (
    CUSTOMER_PHONE,
    make_events_collection,
    make_phone_number,
    make_user_id,
)

CART_ID: str = "aaaaaaaa-1111-1111-1111-111111111111"
ORDER_ID: str = "bbbbbbbb-1111-1111-1111-111111111111"
ORDER_NUMBER: str = "1001"
PRODUCT_ID_PREFIX: str = "1c-product-"
PRICE_TYPE_ID: str = "1c-price-type-wholesale"
UNIT_SOURCE_ID: str = "1c-unit-796"
UNIT_NAME: str = "шт"
DELIVERY_ADDRESS: str = "Москва, Тверская 1, кв. 5"
UNIT_PRICE: str = "19.99"
RECIPIENT_FIRST_NAME: str = "Данил"
RECIPIENT_LAST_NAME: str = "Ковалев"


def make_cart_id(value: str = CART_ID) -> CartId:
    return CartId(UUID(value))


def make_order_id(value: str = ORDER_ID) -> OrderId:
    return OrderId(UUID(value))


def make_order_number(value: str = ORDER_NUMBER) -> OrderNumber:
    return OrderNumber(value=value)


def make_product_id(index: int = 1) -> ProductId:
    return ProductId(value=f"{PRODUCT_ID_PREFIX}{index}")


def make_money(amount: str = UNIT_PRICE, currency: Currency = Currency.RUB) -> Money:
    return Money(Decimal(amount), currency)


def make_quantity(value: int = 1) -> Quantity:
    return Quantity(value=value)


def make_price_type_id(value: str = PRICE_TYPE_ID) -> PriceTypeId:
    return PriceTypeId(value=value)


def make_unit(
    source_id: str | None = UNIT_SOURCE_ID,
    name: str = UNIT_NAME,
) -> UnitOfMeasure:
    """Parameters in the field order of the value, reference first.

    ``UnitOfMeasure`` is built positionally because it is mapped as a
    composite, so a builder taking them the other way round would make
    ``make_unit("1c-unit-796")`` mean a unit *named* "1c-unit-796" — exactly
    the mistake the positional contract exists to prevent.
    """
    return UnitOfMeasure(source_id, name)


def make_delivery_address(value: str = DELIVERY_ADDRESS) -> DeliveryAddress:
    return DeliveryAddress(value=value)


def make_order_comment(value: str = "Позвонить за час до доставки") -> OrderComment:
    return OrderComment(value=value)


def make_recipient(
    first_name: str = RECIPIENT_FIRST_NAME,
    last_name: str | None = RECIPIENT_LAST_NAME,
    phone_number: str = CUSTOMER_PHONE,
) -> Recipient:
    return Recipient(first_name, last_name, make_phone_number(phone_number))


def make_priced_product(
    index: int = 1,
    price: str = UNIT_PRICE,
    currency: Currency = Currency.RUB,
    name: str | None = None,
    unit: UnitOfMeasure | None = None,
    *,
    with_sku: bool = True,
) -> PricedProduct:
    """A priced product numbered ``index``, articled ``SKU-<index>``.

    ``with_sku=False`` is how a test asks for a product 1C never gave an
    article to, which is an ordinary product and not a broken one.
    """
    return PricedProduct(
        product_id=make_product_id(index),
        sku=Sku(value=f"SKU-{index}") if with_sku else None,
        name=ProductName(value=name if name is not None else f"Товар {index}"),
        unit=unit if unit is not None else make_unit(),
        unit_price=make_money(price, currency),
    )


def make_cart(
    items: Mapping[int, int] | None = None,
    user_id: UserId | None = None,
) -> Cart:
    """A cart holding ``{product number: quantity}``, empty by default."""
    cart = Cart.create(
        cart_id=make_cart_id(),
        events_collection=make_events_collection(),
        user_id=user_id if user_id is not None else make_user_id(),
    )

    for index, quantity in (items or {}).items():
        cart.add_item(make_product_id(index), make_quantity(quantity))

    return cart


def price_everything_in(cart: Cart) -> tuple[PricedProduct, ...]:
    """Prices every line of a cart, which is what checkout normally gets."""
    return tuple(
        make_priced_product(index=_index_of(line.product_id)) for line in cart.lines
    )


def make_order_line(
    position: int = 1,
    index: int = 1,
    quantity: int = 1,
    price: str = UNIT_PRICE,
    currency: Currency = Currency.RUB,
    *,
    with_sku: bool = True,
) -> OrderLine:
    priced = make_priced_product(
        index=index,
        price=price,
        currency=currency,
        with_sku=with_sku,
    )
    return OrderLine(
        position=position,
        product_id=priced.product_id,
        sku=priced.sku,
        name=priced.name,
        unit=priced.unit,
        unit_price=priced.unit_price,
        quantity=make_quantity(quantity),
    )


def make_placement(
    lines: tuple[OrderLine, ...] | None = None,
    customer_id: UserId | None = None,
    price_type_id: str = PRICE_TYPE_ID,
    comment: str | None = None,
) -> Placement:
    return Placement(
        customer_id=customer_id if customer_id is not None else make_user_id(),
        lines=lines if lines is not None else (make_order_line(),),
        delivery_address=make_delivery_address(),
        recipient=make_recipient(),
        comment=None if comment is None else make_order_comment(comment),
        price_type_id=make_price_type_id(price_type_id),
    )


def make_checkout(
    cart: Cart,
    priced_products: tuple[PricedProduct, ...] | None = None,
    price_type_id: str = PRICE_TYPE_ID,
    comment: str | None = None,
    delivery_address: str = DELIVERY_ADDRESS,
) -> Checkout:
    return Checkout(
        cart=cart,
        priced_products=(
            priced_products if priced_products is not None else price_everything_in(cart)
        ),
        delivery_address=make_delivery_address(delivery_address),
        recipient=make_recipient(),
        comment=None if comment is None else make_order_comment(comment),
        price_type_id=make_price_type_id(price_type_id),
    )


def make_order(
    status: OrderStatus = OrderStatus.NEW,
    lines: tuple[OrderLine, ...] | None = None,
    customer_id: UserId | None = None,
    price_type_id: str = PRICE_TYPE_ID,
    events_collection: EventsCollection | None = None,
) -> tuple[Order, EventsCollection]:
    """A placed order in ``status``, together with what it reports to.

    The status is reached by calling the real transitions rather than assigning
    the field, because an order that arrived at ``SHIPPED`` any other way is a
    state production never produces.
    """
    collection = (
        events_collection if events_collection is not None else make_events_collection()
    )
    order = Order.place(
        order_id=make_order_id(),
        order_number=make_order_number(),
        events_collection=collection,
        placement=make_placement(
            lines=lines,
            customer_id=customer_id,
            price_type_id=price_type_id,
        ),
    )
    _drive_to(order, status)

    return order, collection


def make_order_access_context(
    subject: User,
    order_customer: User,
) -> OrderAccessContext:
    """One person proposing to act upon the order of another.

    Takes the customer as a ``User`` and hands the context their id, because
    that is the whole point of the context: it carries a ``UserId`` so nothing
    in ``domain/users`` learns about orders.
    """
    return OrderAccessContext(subject=subject, order_customer_id=order_customer.id)


def _index_of(product_id: ProductId) -> int:
    return int(product_id.value.removeprefix(PRODUCT_ID_PREFIX))


_ADVANCE: Final[Mapping[OrderStatus, Callable[[Order], None]]] = {
    OrderStatus.CONFIRMED: Order.confirm,
    OrderStatus.SHIPPED: Order.ship,
    OrderStatus.COMPLETED: Order.complete,
}

_LIFECYCLE: Final[tuple[OrderStatus, ...]] = (
    OrderStatus.NEW,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.COMPLETED,
)


def _drive_to(order: Order, status: OrderStatus) -> None:
    if status is OrderStatus.CANCELLED:
        order.cancel(initiated_by=CancellationInitiator.CUSTOMER)
        return

    for step in _LIFECYCLE[1 : _LIFECYCLE.index(status) + 1]:
        _ADVANCE[step](order)
