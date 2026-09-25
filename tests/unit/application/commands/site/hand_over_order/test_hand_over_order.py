"""Sending one queued order to the site, and recording what the site said.

The interesting decisions: a handover that is not pending any more is left
alone rather than repeated, a customer who cancelled before their turn comes
is withdrawn instead of sent, an outage is retried with a growing delay
without raising, and a refusal is recorded once and announced to staff. The
submission itself has to be built from the order's own snapshot — never from
whatever the catalog says today.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from goldy.application.commands.site.hand_over_order.command import (
    HandOverOrderCommand,
    HandoverOutcome,
)
from goldy.application.commands.site.hand_over_order.handler import (
    HandOverOrderHandler,
    retry_delay,
)
from goldy.application.common.events import OrderHandoverRejected
from goldy.application.common.ports.site import HandoverState
from goldy.application.common.views.order import OrderLineView, OrderView
from goldy.application.error import (
    SiteCustomerNotLinkedError,
    SiteOrderRejectedError,
    SiteUnavailableError,
)
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from goldy.domain.users.values.user_id import UserId
from tests.unit.factories.order_factories import make_order_line_view, make_order_view
from tests.unit.factories.shop_factories import RECIPIENT_FIRST_NAME, RECIPIENT_LAST_NAME
from tests.unit.stubs.orders import StubOrderQueryGateway
from tests.unit.stubs.site import (
    InMemoryOrderHandoverDao,
    InMemorySiteLinkQueryGateway,
    ScriptedSiteOrders,
    site_link_view,
    site_order_status,
)

ORDER_ID = UUID("eeeeeeee-1111-1111-1111-111111111111")


async def _pending_order(
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    status: OrderStatus = OrderStatus.NEW,
    lines: tuple[OrderLineView, ...] | None = None,
) -> OrderView:
    """Queues an order and puts its card in the read model, as ``schedule`` would."""
    view = make_order_view(order_id=str(ORDER_ID), status=status, lines=lines)
    order_query_gateway.cards[OrderId(view.id)] = view
    await handover_dao.schedule(OrderId(view.id))
    return view


def test_retry_delay_doubles_up_to_an_hour_and_no_further() -> None:
    assert retry_delay(0) == timedelta(minutes=1)
    assert retry_delay(1) == timedelta(minutes=2)
    assert retry_delay(3) == timedelta(minutes=8)
    assert retry_delay(6) == timedelta(hours=1)
    assert retry_delay(20) == timedelta(hours=1)


async def test_an_order_never_queued_is_skipped(
    hand_over_order_handler: HandOverOrderHandler,
    site_orders: ScriptedSiteOrders,
) -> None:
    outcome = await hand_over_order_handler.handle(
        HandOverOrderCommand(order_id=ORDER_ID)
    )

    assert outcome is HandoverOutcome.SKIPPED
    assert site_orders.submitted == []


async def test_a_handover_that_is_no_longer_pending_is_skipped(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    """An accepted order is not resubmitted just because it comes up again."""
    view = await _pending_order(handover_dao, order_query_gateway)
    await handover_dao.mark_accepted(OrderId(view.id), site_order_status(str(view.id)))

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.SKIPPED
    assert site_orders.submitted == []


async def test_a_cancelled_order_is_withdrawn_rather_than_sent(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = await _pending_order(
        handover_dao,
        order_query_gateway,
        status=OrderStatus.CANCELLED,
    )

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.WITHDRAWN
    assert handover_dao.rows[OrderId(view.id)].state is HandoverState.WITHDRAWN
    assert site_orders.submitted == []


async def test_an_order_that_has_since_disappeared_is_withdrawn(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    site_orders: ScriptedSiteOrders,
) -> None:
    """No card in the read model is the same refusal as a cancelled one."""
    await handover_dao.schedule(OrderId(ORDER_ID))

    outcome = await hand_over_order_handler.handle(
        HandOverOrderCommand(order_id=ORDER_ID)
    )

    assert outcome is HandoverOutcome.WITHDRAWN
    assert handover_dao.rows[OrderId(ORDER_ID)].state is HandoverState.WITHDRAWN
    assert site_orders.submitted == []


async def test_a_site_outage_is_retried_later_without_raising(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)
    site_orders.submit_errors.append(SiteUnavailableError("the site did not answer"))

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.RETRY
    row = handover_dao.rows[OrderId(view.id)]
    assert row.state is HandoverState.PENDING
    assert row.attempts == 1
    assert row.last_error == "the site did not answer"
    now = datetime.now(UTC)
    assert now + timedelta(seconds=50) < row.next_attempt_at < now + timedelta(seconds=70)


async def test_a_price_refusal_is_recorded_and_announced_to_staff(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
    events_collection: EventsCollection,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)
    site_orders.submit_errors.append(
        SiteOrderRejectedError("prices moved", code="prices_changed"),
    )

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.REJECTED
    row = handover_dao.rows[OrderId(view.id)]
    assert row.state is HandoverState.REJECTED
    assert row.error_code == "prices_changed"
    (event,) = events_collection.events
    assert isinstance(event, OrderHandoverRejected)
    assert event.order_id == view.id
    assert event.order_number == view.number
    assert event.code == "prices_changed"


async def test_the_site_forgetting_the_customer_is_recorded_under_its_own_code(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
    events_collection: EventsCollection,
) -> None:
    """No ``code`` travels on this error, so the handler names it itself."""
    view = await _pending_order(handover_dao, order_query_gateway)
    site_orders.submit_errors.append(SiteCustomerNotLinkedError("gone"))

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.REJECTED
    assert handover_dao.rows[OrderId(view.id)].error_code == "customer_not_linked"
    (event,) = events_collection.events
    assert event.code == "customer_not_linked"


async def test_a_successful_submission_is_accepted(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)

    outcome = await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert outcome is HandoverOutcome.ACCEPTED
    row = handover_dao.rows[OrderId(view.id)]
    assert row.state is HandoverState.ACCEPTED
    assert row.site is not None
    assert row.site.external_id == str(view.id)


async def test_the_order_goes_as_a_guest_when_the_customer_is_not_linked(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)

    await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert site_orders.submitted[0].subject is None


async def test_the_order_carries_the_customers_site_subject_when_linked(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_links: InMemorySiteLinkQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)
    site_links.links[UserId(view.customer_id)] = site_link_view()

    await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert site_orders.submitted[0].subject == str(view.customer_id)


async def test_the_submission_is_built_from_the_orders_own_lines(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    lines = (
        make_order_line_view(position=1, index=7, quantity=3, price="150.00"),
        make_order_line_view(position=2, index=9, quantity=1, price="20.00"),
    )
    view = await _pending_order(handover_dao, order_query_gateway, lines=lines)

    await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    submission = site_orders.submitted[0]
    assert submission.external_id == str(view.id)
    assert submission.number == view.number
    assert [
        (item.product_id.value, item.quantity, item.unit_price)
        for item in submission.items
    ] == [(line.product_id, line.quantity, line.unit_price.amount) for line in lines]
    assert submission.expected_total == view.total.amount
    assert submission.recipient_phone == view.recipient_phone_number
    assert submission.address == view.delivery_address
    assert submission.comment == view.comment


async def test_the_recipient_name_joins_first_and_last_name(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = await _pending_order(handover_dao, order_query_gateway)

    await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    expected = f"{RECIPIENT_FIRST_NAME} {RECIPIENT_LAST_NAME}"
    assert site_orders.submitted[0].recipient_name == expected


async def test_the_recipient_name_is_just_the_first_name_without_a_last_name(
    hand_over_order_handler: HandOverOrderHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    site_orders: ScriptedSiteOrders,
) -> None:
    view = make_order_view(order_id=str(ORDER_ID))
    view = replace(view, recipient_last_name=None)
    order_query_gateway.cards[OrderId(view.id)] = view
    await handover_dao.schedule(OrderId(view.id))

    await hand_over_order_handler.handle(HandOverOrderCommand(order_id=view.id))

    assert site_orders.submitted[0].recipient_name == RECIPIENT_FIRST_NAME
