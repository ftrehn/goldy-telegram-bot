"""Two relays running at once, which is the normal case.

``read_pending`` claims its rows with ``FOR UPDATE SKIP LOCKED``, and that is
the whole reason the worker can be scaled past one replica. It cannot be
verified against a stub — the locking *is* the behaviour — so it runs against
Postgres, naming only the port.
"""

import asyncio
from collections.abc import Sequence

import pytest
from dishka import AsyncContainer, Scope

from goldy.application.common.ports.outbox import OutboxCommandGateway, OutboxMessage
from goldy.application.common.ports.transaction_manager import TransactionManager
from tests.integration.arrange import OutboxSeeder

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


def ids(messages: Sequence[OutboxMessage]) -> set[str]:
    return {str(message.id) for message in messages}


async def test_two_relays_never_claim_the_same_message(
    store_outbox_messages: OutboxSeeder,
    worker_container: AsyncContainer,
) -> None:
    """Both scopes read while the other still holds its rows.

    The claims are taken before either commits, which is exactly the window a
    second replica hits in production. Without ``SKIP LOCKED`` the second reader
    would block on the first instead of taking what is left, and both would end
    up publishing the same events.
    """
    await store_outbox_messages(4)

    async with (
        worker_container(scope=Scope.REQUEST) as first,
        worker_container(scope=Scope.REQUEST) as second,
    ):
        first_gateway = await first.get(OutboxCommandGateway)
        second_gateway = await second.get(OutboxCommandGateway)

        claimed_first = await first_gateway.read_pending(limit=2)
        claimed_second = await second_gateway.read_pending(limit=2)

        await (await first.get(TransactionManager)).commit()
        await (await second.get(TransactionManager)).commit()

    assert len(claimed_first) == 2
    assert not ids(claimed_first) & ids(claimed_second)


async def test_a_second_relay_finds_nothing_left_to_claim(
    store_outbox_messages: OutboxSeeder,
    worker_container: AsyncContainer,
) -> None:
    """The point of skipping rather than waiting: the loser does not stall.

    A blocked second replica would hold a connection for the length of the
    first one's batch and then publish nothing anyway.
    """
    await store_outbox_messages(2)

    async with (
        worker_container(scope=Scope.REQUEST) as first,
        worker_container(scope=Scope.REQUEST) as second,
    ):
        await (await first.get(OutboxCommandGateway)).read_pending(limit=10)

        left_over = await asyncio.wait_for(
            (await second.get(OutboxCommandGateway)).read_pending(limit=10),
            timeout=5,
        )

        await (await first.get(TransactionManager)).commit()
        await (await second.get(TransactionManager)).commit()

    assert left_over == []
