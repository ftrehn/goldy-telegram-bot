"""Bringing a handed-over order in line with the site's feed (ADR-0004).

Only orders the handover actually sent may be moved this way, a move only ever
goes forward through the aggregate's own transitions, and applying the same
status twice must change nothing the second time — the feed is delivered
at-least-once, exactly like everything else in this project.
"""

from datetime import UTC, datetime

from goldy.application.commands.site.apply_site_order_status.command import (
    ApplySiteOrderStatusCommand,
)
from goldy.application.commands.site.apply_site_order_status.handler import (
    ApplySiteOrderStatusHandler,
)
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.values.cancellation_initiator import CancellationInitiator
from goldy.domain.orders.values.order_id import OrderId
from goldy.domain.orders.values.order_status import OrderStatus
from tests.unit.application.commands.site.conftest import OrderSeeder
from tests.unit.factories.shop_factories import make_order
from tests.unit.stubs.orders import InMemoryOrderCommandGateway
from tests.unit.stubs.site import InMemoryOrderHandoverDao, site_order_status


def _status(order: Order, state: str) -> ApplySiteOrderStatusCommand:
    return ApplySiteOrderStatusCommand(
        status=site_order_status(str(order.id), state=state),
    )


async def test_a_handover_that_was_never_accepted_is_left_alone(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    handover_dao: InMemoryOrderHandoverDao,
    order_command_gateway: InMemoryOrderCommandGateway,
) -> None:
    """A ``PENDING`` — or missing — handover has nothing the feed may move.

    The order does not belong to the site yet, whatever it says about it.
    """
    order, _ = make_order(status=OrderStatus.NEW)
    order_command_gateway.orders[order.id] = order
    await handover_dao.schedule(OrderId(order.id))

    moved = await apply_site_order_status_handler.handle(_status(order, "confirmed"))

    assert moved is False
    assert order.status is OrderStatus.NEW


async def test_an_order_the_bot_never_handed_over_at_all_is_left_alone(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    order_command_gateway: InMemoryOrderCommandGateway,
) -> None:
    order, _ = make_order(status=OrderStatus.NEW)
    order_command_gateway.orders[order.id] = order

    moved = await apply_site_order_status_handler.handle(_status(order, "confirmed"))

    assert moved is False
    assert order.status is OrderStatus.NEW


async def test_confirmed_moves_a_new_order_forward(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    order = await seed_accepted_order(OrderStatus.NEW)

    moved = await apply_site_order_status_handler.handle(_status(order, "confirmed"))

    assert moved is True
    assert order.status is OrderStatus.CONFIRMED


async def test_completed_from_new_confirms_and_then_completes(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    """The site has no "shipped" — an order collected at the warehouse never ships."""
    order = await seed_accepted_order(OrderStatus.NEW)

    moved = await apply_site_order_status_handler.handle(_status(order, "completed"))

    assert moved is True
    assert order.status is OrderStatus.COMPLETED


async def test_completed_from_confirmed_completes_directly(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    order = await seed_accepted_order(OrderStatus.CONFIRMED)

    moved = await apply_site_order_status_handler.handle(_status(order, "completed"))

    assert moved is True
    assert order.status is OrderStatus.COMPLETED


async def test_cancelled_cancels_on_the_shops_behalf(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    order = await seed_accepted_order(OrderStatus.NEW)

    moved = await apply_site_order_status_handler.handle(_status(order, "cancelled"))

    assert moved is True
    assert order.status is OrderStatus.CANCELLED
    assert order.cancelled_by is CancellationInitiator.SHOP
    assert order.cancelled_by_user_id is None
    assert order.cancellation_reason is None


async def test_a_terminal_order_is_never_touched_again(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    order = await seed_accepted_order(OrderStatus.COMPLETED)

    moved = await apply_site_order_status_handler.handle(_status(order, "cancelled"))

    assert moved is False
    assert order.status is OrderStatus.COMPLETED


async def test_replaying_the_same_status_changes_nothing(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    seed_accepted_order: OrderSeeder,
) -> None:
    order = await seed_accepted_order(OrderStatus.NEW)
    first = await apply_site_order_status_handler.handle(_status(order, "confirmed"))

    second = await apply_site_order_status_handler.handle(_status(order, "confirmed"))

    assert first is True
    assert second is False
    assert order.status is OrderStatus.CONFIRMED


async def test_the_feeds_latest_word_replaces_the_stored_one_either_way(
    apply_site_order_status_handler: ApplySiteOrderStatusHandler,
    handover_dao: InMemoryOrderHandoverDao,
    seed_accepted_order: OrderSeeder,
) -> None:
    """A status the order cannot reach is still worth recording, for the day.

    ``moved`` answers "did the order move", not "was the feed's word kept" —
    ``record_site_status`` writes the snapshot before ``_follow`` is asked
    anything about the transition.
    """
    order = await seed_accepted_order(OrderStatus.COMPLETED)
    later = datetime(2026, 9, 26, 9, 0, tzinfo=UTC)

    moved = await apply_site_order_status_handler.handle(
        ApplySiteOrderStatusCommand(
            status=site_order_status(str(order.id), state="cancelled", updated_at=later),
        ),
    )

    row = handover_dao.rows[OrderId(order.id)]
    assert moved is False
    assert row.site is not None
    assert row.site.updated_at == later
