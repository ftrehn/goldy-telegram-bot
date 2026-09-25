"""The order-handover command handlers (ADR-0004), assembled from the shared stubs.

One conftest for the whole ``site`` package, the way ``commands/orders`` has
one: scheduling, handing over, applying the site's feed and the runner that
ticks the two together all share the same handover row and the same
``ScriptedSiteOrders``, and splitting the fixtures per handler would only make
that sharing harder to see.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

import pytest

from goldy.application.commands.site.apply_site_order_status.handler import (
    ApplySiteOrderStatusHandler,
)
from goldy.application.commands.site.hand_over_order.handler import HandOverOrderHandler
from goldy.application.commands.site.order_handover_runner import OrderHandoverRunner
from goldy.application.commands.site.schedule_order_handover.handler import (
    ScheduleOrderHandoverHandler,
)
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from tests.unit.factories.shop_factories import make_order
from tests.unit.stubs.orders import InMemoryOrderCommandGateway, StubOrderQueryGateway
from tests.unit.stubs.site import (
    HandoverCommandSender,
    InMemoryOrderHandoverDao,
    InMemorySiteLinkQueryGateway,
    ScriptedSiteOrders,
    site_order_status,
)

type OrderSeeder = Callable[..., Awaitable[Order]]


@pytest.fixture()
def handover_dao() -> InMemoryOrderHandoverDao:
    return InMemoryOrderHandoverDao()


@pytest.fixture()
def site_orders() -> ScriptedSiteOrders:
    return ScriptedSiteOrders()


@pytest.fixture()
def site_links() -> InMemorySiteLinkQueryGateway:
    """Nobody is linked to the site unless a test links them."""
    return InMemorySiteLinkQueryGateway()


@pytest.fixture()
def order_query_gateway() -> StubOrderQueryGateway:
    return StubOrderQueryGateway()


@pytest.fixture()
def order_command_gateway() -> InMemoryOrderCommandGateway:
    return InMemoryOrderCommandGateway()


@pytest.fixture()
def schedule_order_handover_handler(
    handover_dao: InMemoryOrderHandoverDao,
) -> ScheduleOrderHandoverHandler:
    return ScheduleOrderHandoverHandler(handover_dao)


@pytest.fixture()
def hand_over_order_handler(
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    site_orders: ScriptedSiteOrders,
    events_collection: EventsCollection,
) -> HandOverOrderHandler:
    return HandOverOrderHandler(
        handover_dao,
        order_query_gateway,
        site_links,
        site_orders,
        events_collection,
    )


@pytest.fixture()
def apply_site_order_status_handler(
    handover_dao: InMemoryOrderHandoverDao,
    order_command_gateway: InMemoryOrderCommandGateway,
) -> ApplySiteOrderStatusHandler:
    return ApplySiteOrderStatusHandler(handover_dao, order_command_gateway)


@pytest.fixture()
def handover_sender(
    hand_over_order_handler: HandOverOrderHandler,
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
) -> HandoverCommandSender:
    """Runs ``HandOverOrderCommand`` and ``ApplySiteOrderStatusCommand`` for real.

    The runner sends commands rather than calling handlers directly, so its own
    tests need something that actually answers them — with the real handlers,
    over the same stubs the runner was given.
    """
    return HandoverCommandSender(hand_over_order_handler, apply_site_order_status_handler)


@pytest.fixture()
def order_handover_runner(
    handover_sender: HandoverCommandSender,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
) -> OrderHandoverRunner:
    return OrderHandoverRunner(handover_sender, handover_dao, site_orders)


@pytest.fixture()
def seed_accepted_order(
    order_command_gateway: InMemoryOrderCommandGateway,
    handover_dao: InMemoryOrderHandoverDao,
    events_collection: EventsCollection,
) -> OrderSeeder:
    """Places an order and marks its handover accepted, as a successful submit would.

    ``apply_site_order_status`` and the runner's feed side only ever see orders
    the handover has already sent — the site's feed does not mention an order
    it was never handed.
    """

    async def seed(
        status: OrderStatus = OrderStatus.NEW,
        site_updated_at: datetime | None = None,
    ) -> Order:
        order, _ = make_order(status=status, events_collection=events_collection)
        order_command_gateway.orders[order.id] = order
        await handover_dao.schedule(OrderId(order.id))
        await handover_dao.mark_accepted(
            OrderId(order.id),
            site_order_status(str(order.id), updated_at=site_updated_at),
        )
        return order

    return seed
