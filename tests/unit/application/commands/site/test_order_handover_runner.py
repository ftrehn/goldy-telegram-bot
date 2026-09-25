"""One tick of handing orders to the site and reading their statuses back.

Not a handler test: the runner sends commands rather than deciding anything
itself, so what is worth pinning down is that it sends exactly one command per
due order, that it leaves an order alone before its retry is due, and that
reading the feed is skipped entirely — never even asking the site — when this
client has nothing accepted to ask about.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from goldy.application.commands.site.hand_over_order.command import (
    HandOverOrderCommand,
    HandoverOutcome,
)
from goldy.application.commands.site.order_handover_runner import OrderHandoverRunner
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from tests.unit.application.commands.site.conftest import OrderSeeder
from tests.unit.factories.order_factories import make_order_view
from tests.unit.stubs.orders import StubOrderQueryGateway
from tests.unit.stubs.site import (
    HandoverCommandSender,
    InMemoryOrderHandoverDao,
    ScriptedSiteOrders,
    site_order_status,
)

FIRST_ORDER = UUID("11111111-2222-2222-2222-222222222221")
SECOND_ORDER = UUID("11111111-2222-2222-2222-222222222222")


async def _queue(
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    order_id: UUID,
) -> None:
    """A pending handover with a card in the read model, so a real send succeeds."""
    order_query_gateway.cards[OrderId(order_id)] = make_order_view(order_id=str(order_id))
    await handover_dao.schedule(OrderId(order_id))


async def test_hand_over_due_sends_one_command_per_due_order(
    order_handover_runner: OrderHandoverRunner,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    handover_sender: HandoverCommandSender,
) -> None:
    await _queue(handover_dao, order_query_gateway, FIRST_ORDER)
    await _queue(handover_dao, order_query_gateway, SECOND_ORDER)

    outcomes = await order_handover_runner.hand_over_due()

    sent = [
        r.order_id
        for r in handover_sender.requests
        if isinstance(r, HandOverOrderCommand)
    ]
    assert sorted(sent) == sorted((FIRST_ORDER, SECOND_ORDER))
    assert outcomes == Counter({HandoverOutcome.ACCEPTED: 2})


async def test_an_order_whose_retry_has_not_come_due_yet_is_left_for_later(
    order_handover_runner: OrderHandoverRunner,
    handover_dao: InMemoryOrderHandoverDao,
    order_query_gateway: StubOrderQueryGateway,
    handover_sender: HandoverCommandSender,
) -> None:
    await _queue(handover_dao, order_query_gateway, FIRST_ORDER)
    await handover_dao.mark_retry(OrderId(FIRST_ORDER), timedelta(minutes=10), "slow")

    outcomes = await order_handover_runner.hand_over_due()

    assert outcomes == Counter()
    assert handover_sender.requests == []


async def test_pull_statuses_does_not_call_the_site_when_nothing_was_ever_accepted(
    order_handover_runner: OrderHandoverRunner,
    site_orders: ScriptedSiteOrders,
) -> None:
    """This client's feed has nothing in it before its first accepted order."""
    moved = await order_handover_runner.pull_statuses()

    assert moved == 0
    assert site_orders.feed_since == []


async def test_pull_statuses_starts_five_minutes_before_the_latest_seen_change(
    order_handover_runner: OrderHandoverRunner,
    site_orders: ScriptedSiteOrders,
    seed_accepted_order: OrderSeeder,
) -> None:
    latest = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    order = await seed_accepted_order(site_updated_at=latest)
    site_orders.feed_pages = [
        [site_order_status(str(order.id), state="confirmed", updated_at=latest)],
    ]

    moved = await order_handover_runner.pull_statuses()

    assert moved == 1
    assert site_orders.feed_since == [latest - timedelta(minutes=5)]
    assert order.status is OrderStatus.CONFIRMED
