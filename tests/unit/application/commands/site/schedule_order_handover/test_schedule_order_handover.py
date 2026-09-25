"""Queuing a freshly placed order for the site (ADR-0004).

The one thing that matters here is idempotency: the order id is the queue's
primary key, so a redelivered ``OrderPlaced`` must not queue the order twice.
Sending it is a separate command, tested on its own.
"""

from uuid import UUID

from goldy.application.commands.site.schedule_order_handover.command import (
    ScheduleOrderHandoverCommand,
)
from goldy.application.commands.site.schedule_order_handover.handler import (
    ScheduleOrderHandoverHandler,
)
from goldy.application.common.ports.site import HandoverState
from goldy.domain.orders.values.order_id import OrderId
from tests.unit.stubs.site import InMemoryOrderHandoverDao

ORDER_ID = UUID("dddddddd-1111-1111-1111-111111111111")


async def test_a_freshly_placed_order_is_queued_pending(
    schedule_order_handover_handler: ScheduleOrderHandoverHandler,
    handover_dao: InMemoryOrderHandoverDao,
) -> None:
    scheduled = await schedule_order_handover_handler.handle(
        ScheduleOrderHandoverCommand(order_id=ORDER_ID),
    )

    assert scheduled is True
    assert handover_dao.rows[OrderId(ORDER_ID)].state is HandoverState.PENDING


async def test_a_redelivered_order_placed_event_queues_nothing_twice(
    schedule_order_handover_handler: ScheduleOrderHandoverHandler,
    handover_dao: InMemoryOrderHandoverDao,
) -> None:
    first = await schedule_order_handover_handler.handle(
        ScheduleOrderHandoverCommand(order_id=ORDER_ID),
    )
    second = await schedule_order_handover_handler.handle(
        ScheduleOrderHandoverCommand(order_id=ORDER_ID),
    )

    assert first is True
    assert second is False
    assert len(handover_dao.rows) == 1
