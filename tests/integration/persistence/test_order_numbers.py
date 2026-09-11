"""Order numbers under concurrency, where a counter row would fall over.

The number is drawn from a Postgres sequence rather than from a row somebody
increments, and the difference only shows when two people confirm their carts
at the same instant. A counter row has to be locked to be read safely, which
puts every checkout in the shop in a queue behind every other; a sequence hands
out a value without waiting for the transaction that asked for it.

The price of that is gaps, and the last test writes the price down rather than
treating it as a defect. Gapless numbering means the lock, and the lock means
the queue.
"""

import asyncio
from typing import Final

import pytest
from dishka import AsyncContainer, Scope
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from goldy.application.common.ports.orders import OrderCommandGateway
from goldy.application.common.ports.transaction_manager import TransactionManager
from goldy.domain.common.events_collection import EventsCollection
from goldy.domain.orders.entities.order import Order
from goldy.domain.orders.ports.id_generator import OrderIdGenerator
from goldy.domain.orders.ports.number_generator import OrderNumberGenerator
from goldy.domain.users.values.user_id import UserId
from tests.integration.arrange import UserSeeder
from tests.unit.factories.shop_factories import make_placement

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]

CHECKOUTS: Final[int] = 10
"""Enough connections to collide on, and fewer than the pool can hand out."""


async def test_simultaneous_draws_never_repeat_a_number(
    worker_container: AsyncContainer,
) -> None:
    """Ten requests on ten connections, asking at the same time."""
    drawn = await asyncio.gather(
        *(_draw(worker_container) for _ in range(CHECKOUTS)),
    )

    assert len(set(drawn)) == CHECKOUTS


async def test_simultaneous_checkouts_all_land_with_a_number_of_their_own(
    seed_user: UserSeeder,
    worker_container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The unique index and the sequence together, at the only moment it matters.

    Ten whole orders rather than ten numbers, because the number is drawn
    inside the transaction that writes the order: a sequence that queued, or an
    index that refused, would show up here as an order that never landed.
    """
    seeded = await seed_user()

    await asyncio.gather(
        *(_place(worker_container, seeded.id) for _ in range(CHECKOUTS)),
    )

    async with engine.connect() as connection:
        numbers = (
            (await connection.execute(text("SELECT number FROM orders"))).scalars().all()
        )

    assert len(numbers) == CHECKOUTS
    assert len(set(numbers)) == CHECKOUTS


async def test_a_number_drawn_by_a_transaction_that_failed_is_not_reissued(
    worker_container: AsyncContainer,
) -> None:
    """The gaps are the deal, and they are the right side of it.

    A number that came back to the pool would have to be held under a lock
    until its transaction ended, which is exactly the queue the sequence exists
    to avoid.
    """
    async with worker_container(scope=Scope.REQUEST) as abandoned:
        numbers: OrderNumberGenerator = await abandoned.get(OrderNumberGenerator)
        transaction: TransactionManager = await abandoned.get(TransactionManager)
        first = await numbers()
        await transaction.rollback()

    second = await _draw(worker_container)

    assert second != str(first)


async def _draw(container: AsyncContainer) -> str:
    """One request's worth of "give me the next number", committed on its own."""
    async with container(scope=Scope.REQUEST) as scope:
        numbers: OrderNumberGenerator = await scope.get(OrderNumberGenerator)
        transaction: TransactionManager = await scope.get(TransactionManager)
        drawn = await numbers()
        await transaction.commit()
        return str(drawn)


async def _place(container: AsyncContainer, customer_id: UserId) -> None:
    """One whole checkout, from drawing the number to committing the order."""
    async with container(scope=Scope.REQUEST) as scope:
        ids: OrderIdGenerator = await scope.get(OrderIdGenerator)
        numbers: OrderNumberGenerator = await scope.get(OrderNumberGenerator)
        gateway: OrderCommandGateway = await scope.get(OrderCommandGateway)
        transaction: TransactionManager = await scope.get(TransactionManager)
        events: EventsCollection = await scope.get(EventsCollection)

        order = Order.place(
            order_id=ids(),
            order_number=await numbers(),
            events_collection=events,
            placement=make_placement(customer_id=customer_id),
        )
        await gateway.add(order)
        await transaction.commit()
