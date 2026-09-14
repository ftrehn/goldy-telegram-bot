"""The order query handlers over one stubbed read-side gateway."""

import pytest

from goldy.application.common.services.user_provider import UserProvider
from goldy.application.queries.orders.get_last_delivery_address.handler import (
    GetLastDeliveryAddressHandler,
)
from goldy.application.queries.orders.get_order.handler import GetOrderHandler
from goldy.application.queries.orders.list_my_orders.handler import ListMyOrdersHandler
from goldy.application.queries.orders.list_orders.handler import ListOrdersHandler
from goldy.domain.users.services.access_service import AccessService
from tests.unit.stubs.identity import StubIdentityProvider
from tests.unit.stubs.orders import StubOrderQueryGateway


@pytest.fixture()
def order_query_gateway() -> StubOrderQueryGateway:
    return StubOrderQueryGateway()


@pytest.fixture()
def get_order_handler(
    user_provider: UserProvider,
    order_query_gateway: StubOrderQueryGateway,
    access_service: AccessService,
) -> GetOrderHandler:
    return GetOrderHandler(user_provider, order_query_gateway, access_service)


@pytest.fixture()
def list_my_orders_handler(
    identity_provider: StubIdentityProvider,
    order_query_gateway: StubOrderQueryGateway,
) -> ListMyOrdersHandler:
    return ListMyOrdersHandler(identity_provider, order_query_gateway)


@pytest.fixture()
def list_orders_handler(
    user_provider: UserProvider,
    order_query_gateway: StubOrderQueryGateway,
    access_service: AccessService,
) -> ListOrdersHandler:
    return ListOrdersHandler(user_provider, order_query_gateway, access_service)


@pytest.fixture()
def get_last_delivery_address_handler(
    identity_provider: StubIdentityProvider,
    order_query_gateway: StubOrderQueryGateway,
) -> GetLastDeliveryAddressHandler:
    return GetLastDeliveryAddressHandler(identity_provider, order_query_gateway)
