"""Reading orders: one card guarded by two halves of one rule, two listings."""

from uuid import UUID

import pytest

from goldy.application.common.query_params.order_filters import OrderSortField
from goldy.application.common.query_params.sorting import SortingOrder
from goldy.application.common.views.order import OrderListView
from goldy.application.error import OrderNotFoundError
from goldy.application.queries.orders.get_last_delivery_address.handler import (
    GetLastDeliveryAddressHandler,
)
from goldy.application.queries.orders.get_last_delivery_address.query import (
    GetLastDeliveryAddressQuery,
)
from goldy.application.queries.orders.get_order.handler import GetOrderHandler
from goldy.application.queries.orders.get_order.query import GetOrderQuery
from goldy.application.queries.orders.list_my_orders.handler import ListMyOrdersHandler
from goldy.application.queries.orders.list_my_orders.query import ListMyOrdersQuery
from goldy.application.queries.orders.list_orders.handler import ListOrdersHandler
from goldy.application.queries.orders.list_orders.query import ListOrdersQuery
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.errors import AuthorizationError
from goldy.domain.users.values.user_role import UserRole
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.factories.order_factories import (
    make_order_list_item_view,
    make_order_view,
)
from tests.unit.factories.shop_factories import DELIVERY_ADDRESS
from tests.unit.stubs.orders import StubOrderQueryGateway

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}
OTHER_CUSTOMER = {"phone_number": "+79994444444", "external_id": "444"}
MANAGER = {"phone_number": "+79992222222", "external_id": "222"}

UNKNOWN_ORDER = UUID(int=999)
PAGE_SIZE: int = 5


async def test_the_buyer_opens_their_own_card(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    get_order_handler: GetOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    card = make_order_view(customer_id=customer.id)
    order_query_gateway.cards[OrderId(card.id)] = card

    view = await get_order_handler.handle(GetOrderQuery(order_id=card.id))

    assert view is card


async def test_staff_open_anybodys_card(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    get_order_handler: GetOrderHandler,
) -> None:
    """The same rule, satisfied by its other half — no branch on who is asking."""
    customer = await seed_user(**CUSTOMER)
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    card = make_order_view(customer_id=customer.id)
    order_query_gateway.cards[OrderId(card.id)] = card

    view = await get_order_handler.handle(GetOrderQuery(order_id=card.id))

    assert view is card


async def test_another_customer_is_refused_the_card(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    get_order_handler: GetOrderHandler,
) -> None:
    owner = await seed_user(**CUSTOMER)
    stranger = await seed_user(**OTHER_CUSTOMER)
    acting_as(stranger.id)
    card = make_order_view(customer_id=owner.id)
    order_query_gateway.cards[OrderId(card.id)] = card

    with pytest.raises(AuthorizationError):
        await get_order_handler.handle(GetOrderQuery(order_id=card.id))


async def test_a_card_that_does_not_exist(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    get_order_handler: GetOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(OrderNotFoundError):
        await get_order_handler.handle(GetOrderQuery(order_id=UNKNOWN_ORDER))


async def test_my_orders_are_read_for_whoever_is_asking(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    list_my_orders_handler: ListMyOrdersHandler,
) -> None:
    """The customer is taken from the identity provider and from nowhere else.

    That is why the query has no field to put somebody else's id into.
    """
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order_query_gateway.listing = OrderListView(
        orders=(make_order_list_item_view(customer_id=customer.id),),
        total=1,
    )

    view = await list_my_orders_handler.handle(ListMyOrdersQuery(limit=PAGE_SIZE))

    assert view.total == 1
    read = order_query_gateway.reads[0]
    assert read.customer_id == customer.id
    assert read.pagination.limit == PAGE_SIZE
    assert read.sorting.sort_by is OrderSortField.CREATED_AT
    assert read.sorting.order is SortingOrder.DESC
    assert read.filters.status is None


async def test_my_orders_can_be_narrowed_to_one_status(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    list_my_orders_handler: ListMyOrdersHandler,
) -> None:
    """Finished orders are in the page by default.

    Filtering is a button somebody presses, because "where is the order I
    placed last spring" is an ordinary question.
    """
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    await list_my_orders_handler.handle(
        ListMyOrdersQuery(status=OrderStatus.COMPLETED),
    )

    assert order_query_gateway.reads[0].filters.status is OrderStatus.COMPLETED


async def test_staff_read_the_whole_queue(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    list_orders_handler: ListOrdersHandler,
) -> None:
    manager = await seed_user(**MANAGER, role=UserRole.MANAGER)
    acting_as(manager.id)
    order_query_gateway.listing = OrderListView(
        orders=(make_order_list_item_view(),),
        total=1,
    )

    view = await list_orders_handler.handle(ListOrdersQuery(limit=PAGE_SIZE))

    assert view.total == 1
    assert order_query_gateway.reads[0].customer_id is None


async def test_a_customer_is_refused_the_queue(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    list_orders_handler: ListOrdersHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    with pytest.raises(AuthorizationError):
        await list_orders_handler.handle(ListOrdersQuery())

    assert order_query_gateway.reads == []


async def test_the_address_of_the_previous_order_is_offered_back(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    order_query_gateway: StubOrderQueryGateway,
    get_last_delivery_address_handler: GetLastDeliveryAddressHandler,
) -> None:
    """Read for whoever is asking, because the query has nobody else to name."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order_query_gateway.last_delivery_address = DELIVERY_ADDRESS

    address = await get_last_delivery_address_handler.handle(
        GetLastDeliveryAddressQuery(),
    )

    assert address == DELIVERY_ADDRESS
    assert order_query_gateway.address_reads == [customer.id]


async def test_a_first_order_has_no_address_to_offer(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    get_last_delivery_address_handler: GetLastDeliveryAddressHandler,
) -> None:
    """An ordinary answer rather than a refusal: the screen draws no button."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)

    address = await get_last_delivery_address_handler.handle(
        GetLastDeliveryAddressQuery(),
    )

    assert address is None
