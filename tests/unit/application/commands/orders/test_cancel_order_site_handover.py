"""Cancelling an order that has already made its way to the site (ADR-0004).

The bot's own status flips on the buyer's own transitions, exactly as in
``test_order_lifecycle.py``; what is new here is the second half — a pending
handover is simply withdrawn from the queue, an accepted one is cancelled on
the site with the customer's subject when they are linked and as a guest when
they are not, a refusal from the site propagates rather than being swallowed,
and an order never handed over touches the site not at all.
"""

import pytest

from goldy.application.commands.orders.cancel_order.command import CancelOrderCommand
from goldy.application.commands.orders.cancel_order.handler import CancelOrderHandler
from goldy.application.common.ports.site import HandoverState
from goldy.application.error import (
    SiteOrderNotCancellableError,
    SiteUnavailableError,
)
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.entities.site_link import SiteLink
from tests.unit.application.conftest import ActingAs, UserSeeder
from tests.unit.stubs.site import (
    InMemoryOrderHandoverDao,
    ScriptedSiteOrders,
    site_order_status,
)

from .conftest import OrderSeeder

CUSTOMER = {"phone_number": "+79991111111", "external_id": "111"}


async def test_a_pending_handover_is_withdrawn_rather_than_reaching_the_site(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)
    await handover_dao.schedule(OrderId(order.id))

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED
    assert handover_dao.rows[OrderId(order.id)].state is HandoverState.WITHDRAWN
    assert site_orders.cancelled == []


async def test_an_accepted_handover_is_cancelled_on_the_site_as_a_guest_when_unlinked(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)
    await handover_dao.schedule(OrderId(order.id))
    await handover_dao.mark_accepted(OrderId(order.id), site_order_status(str(order.id)))

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED
    assert site_orders.cancelled == [(str(order.id), None, None)]


async def test_an_accepted_handover_is_cancelled_with_the_customers_site_subject(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    customer.link_site_account(
        SiteLink.from_site(
            customer_name="Иван Иванов", company_name=None, is_wholesale=False
        ),
    )
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)
    await handover_dao.schedule(OrderId(order.id))
    await handover_dao.mark_accepted(OrderId(order.id), site_order_status(str(order.id)))

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert site_orders.cancelled == [(str(order.id), str(customer.id), None)]


async def test_the_site_refusing_to_cancel_a_worked_order_propagates(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    """A manager already working the order on the site outranks the customer."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)
    await handover_dao.schedule(OrderId(order.id))
    await handover_dao.mark_accepted(OrderId(order.id), site_order_status(str(order.id)))
    site_orders.cancel_errors.append(
        SiteOrderNotCancellableError("the site has this order in work"),
    )

    with pytest.raises(SiteOrderNotCancellableError):
        await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))


async def test_the_site_not_answering_while_cancelling_propagates(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    """Nothing here is cancelled anywhere until the site actually answers."""
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)
    await handover_dao.schedule(OrderId(order.id))
    await handover_dao.mark_accepted(OrderId(order.id), site_order_status(str(order.id)))
    site_orders.cancel_errors.append(SiteUnavailableError("the site did not answer"))

    with pytest.raises(SiteUnavailableError):
        await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))


async def test_an_order_never_handed_over_touches_nothing_on_the_site(
    seed_user: UserSeeder,
    acting_as: ActingAs,
    seed_order: OrderSeeder,
    site_orders: ScriptedSiteOrders,
    cancel_order_handler: CancelOrderHandler,
) -> None:
    customer = await seed_user(**CUSTOMER)
    acting_as(customer.id)
    order = seed_order(customer.id, OrderStatus.NEW)

    await cancel_order_handler.handle(CancelOrderCommand(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED
    assert site_orders.cancelled == []
