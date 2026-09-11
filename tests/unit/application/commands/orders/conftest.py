"""The order command handlers, assembled from the shared stubs.

The pricing service and the price type provider are the real ones rather than
stubs: they are where the read model becomes domain values and where an
unconfigured price list becomes a refusal, and stubbing them would hide exactly
the behaviour these tests exist to hold.
"""

from collections.abc import Callable, Mapping

import pytest

from goldy.application.commands.carts.repeat_order.handler import RepeatOrderHandler
from goldy.application.commands.orders.cancel_order.handler import CancelOrderHandler
from goldy.application.commands.orders.change_delivery_address.handler import (
    ChangeDeliveryAddressHandler,
)
from goldy.application.commands.orders.change_order_status.handler import (
    ChangeOrderStatusHandler,
)
from goldy.application.commands.orders.place_order.handler import PlaceOrderHandler
from goldy.application.common.services.cart_pricing_service import CartPricingService
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.services.purchasable_products_service import (
    PurchasableProductsService,
)
from goldy.application.common.services.user_provider import UserProvider
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.entities.order_line import OrderLine
from goldy.domain.orders.services.checkout_service import CheckoutService
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.services.access_service import AccessService
from goldy.domain.users.values.user_id import UserId
from tests.unit.factories.catalog_factories import make_price_type_view
from tests.unit.factories.shop_factories import (
    make_cart_id,
    make_order,
    make_product_id,
    make_quantity,
)
from tests.unit.stubs.catalog import StubPricingGateway
from tests.unit.stubs.generators import StubOrderIdGenerator, StubOrderNumberGenerator
from tests.unit.stubs.identity import StubIdentityProvider
from tests.unit.stubs.orders import (
    InMemoryCartCommandGateway,
    InMemoryOrderCommandGateway,
)

type CartSeeder = Callable[[UserId, Mapping[int, int]], Cart]
type OrderSeeder = Callable[..., Order]
"""``(customer_id, status=NEW, lines=one line)`` — spelled loosely on purpose.

Only the owner is ever passed positionally. A test that cares about the status
names it, a test that cares about the contents names those, and the great
majority care about neither.
"""


@pytest.fixture()
def cart_gateway(events_collection: EventsCollection) -> InMemoryCartCommandGateway:
    return InMemoryCartCommandGateway(events_collection)


@pytest.fixture()
def order_gateway() -> InMemoryOrderCommandGateway:
    return InMemoryOrderCommandGateway()


@pytest.fixture()
def pricing_gateway() -> StubPricingGateway:
    """A pricing gateway configured with an ordinary price list.

    A test that wants a broken one says so by reassigning ``price_type``.
    """
    return StubPricingGateway(make_price_type_view())


@pytest.fixture()
def price_type_provider(
    identity_provider: StubIdentityProvider,
    pricing_gateway: StubPricingGateway,
) -> PriceTypeProvider:
    return PriceTypeProvider(identity_provider, pricing_gateway)


@pytest.fixture()
def purchasable_products(
    price_type_provider: PriceTypeProvider,
    pricing_gateway: StubPricingGateway,
) -> PurchasableProductsService:
    return PurchasableProductsService(price_type_provider, pricing_gateway)


@pytest.fixture()
def cart_pricing_service(
    price_type_provider: PriceTypeProvider,
    pricing_gateway: StubPricingGateway,
) -> CartPricingService:
    return CartPricingService(price_type_provider, pricing_gateway)


@pytest.fixture()
def order_number_generator() -> StubOrderNumberGenerator:
    return StubOrderNumberGenerator()


@pytest.fixture()
def checkout_service(
    events_collection: EventsCollection,
    order_number_generator: StubOrderNumberGenerator,
) -> CheckoutService:
    return CheckoutService(
        events_collection,
        StubOrderIdGenerator(),
        order_number_generator,
    )


@pytest.fixture()
def place_order_handler(
    user_provider: UserProvider,
    cart_gateway: InMemoryCartCommandGateway,
    cart_pricing_service: CartPricingService,
    checkout_service: CheckoutService,
    order_gateway: InMemoryOrderCommandGateway,
) -> PlaceOrderHandler:
    return PlaceOrderHandler(
        user_provider,
        cart_gateway,
        cart_pricing_service,
        checkout_service,
        order_gateway,
    )


@pytest.fixture()
def cancel_order_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    order_gateway: InMemoryOrderCommandGateway,
) -> CancelOrderHandler:
    return CancelOrderHandler(user_provider, access_service, order_gateway)


@pytest.fixture()
def change_order_status_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    order_gateway: InMemoryOrderCommandGateway,
) -> ChangeOrderStatusHandler:
    return ChangeOrderStatusHandler(user_provider, access_service, order_gateway)


@pytest.fixture()
def change_delivery_address_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    order_gateway: InMemoryOrderCommandGateway,
) -> ChangeDeliveryAddressHandler:
    return ChangeDeliveryAddressHandler(user_provider, access_service, order_gateway)


@pytest.fixture()
def repeat_order_handler(
    user_provider: UserProvider,
    access_service: AccessService,
    order_gateway: InMemoryOrderCommandGateway,
    cart_gateway: InMemoryCartCommandGateway,
    purchasable_products: PurchasableProductsService,
) -> RepeatOrderHandler:
    """A cart command assembled here, where the orders it repeats are seeded.

    It writes to a cart and belongs to ``commands/carts`` for that reason, but
    everything it needs arranging is an order: a customer who owns one, lines
    that point at products the catalog may or may not still hold, and somebody
    else's order to be refused. Duplicating that arrangement next to the cart
    would be a second copy of this file.
    """
    return RepeatOrderHandler(
        user_provider,
        access_service,
        order_gateway,
        cart_gateway,
        purchasable_products,
    )


@pytest.fixture()
def seed_cart(
    cart_gateway: InMemoryCartCommandGateway,
    events_collection: EventsCollection,
) -> CartSeeder:
    """Fills somebody's cart with ``{product number: quantity}``."""

    def seed(user_id: UserId, items: Mapping[int, int]) -> Cart:
        cart = Cart.create(
            cart_id=make_cart_id(),
            events_collection=events_collection,
            user_id=user_id,
        )

        for index, quantity in items.items():
            cart.add_item(make_product_id(index), make_quantity(quantity))

        cart_gateway.carts[user_id] = cart
        return cart

    return seed


@pytest.fixture()
def seed_order(
    order_gateway: InMemoryOrderCommandGateway,
    events_collection: EventsCollection,
) -> OrderSeeder:
    """Puts a placed order in the gateway at the status a test asks for.

    Driven there by the aggregate's own transitions rather than by assigning
    the field, so a seeded order is one the domain agrees could exist.
    """

    def seed(
        customer_id: UserId,
        status: OrderStatus = OrderStatus.NEW,
        lines: tuple[OrderLine, ...] | None = None,
    ) -> Order:
        order, _ = make_order(
            status=status,
            lines=lines,
            customer_id=customer_id,
            events_collection=events_collection,
        )
        order_gateway.orders[order.id] = order
        return order

    return seed
