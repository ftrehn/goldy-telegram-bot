"""The outbox relay, from the scheduled task down to the broker.

Nothing below the ports is stubbed. The rows are in Postgres, the claim is a
real ``SELECT ... FOR UPDATE SKIP LOCKED``, and the publisher is the production
``FastStreamOutboxPublisher`` talking to an in-process FastStream broker — so
the two invariants its docstring promises, a stable ``message_id`` and a JSON
content type, are checked here rather than asserted in prose.
"""

import pytest
from dishka import FromDishka
from taskiq import AsyncBroker

from goldy.application.commands.outbox.relay_outbox.command import RelayOutboxCommand
from goldy.application.common.ports.outbox import OutboxCommandGateway
from goldy.application.common.ports.task_manager.task_keys import (
    RELAY_OUTBOX_TASK_NAME,
)
from goldy.application.common.views.outbox import RelayOutboxResponse
from tests.integration.arrange import CommandSender, OutboxSeeder
from tests.integration.brokers import PublishedEvents
from tests.integration.inject import inject

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.integration,
    pytest.mark.usefixtures("clean_tables"),
]


async def test_the_scheduled_task_drains_the_outbox(
    store_outbox_messages: OutboxSeeder,
    taskiq_broker: AsyncBroker,
    published: PublishedEvents,
) -> None:
    """The whole chain: the name the scheduler fires, through to the broker.

    Kicked by name rather than by calling the function, because the name is the
    part that breaks. A task nobody registered resolves to nothing, and the
    outbox then stops draining without an error anywhere.
    """
    await store_outbox_messages(3)

    task = taskiq_broker.get_all_tasks()[RELAY_OUTBOX_TASK_NAME]
    await (await task.kiq()).wait_result()

    assert len(published.all()) == 3


async def test_a_published_message_carries_its_outbox_id(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """Consumers key idempotency off this, and the row id is what survives a retry."""
    stored = await store_outbox_messages(2)

    await send_worker_command(RelayOutboxCommand())

    assert published.message_ids() == {str(message.id) for message in stored}


async def test_a_published_message_arrives_as_json(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """Publishing the stored payload as-is would send a string and say so.

    The row holds JSON *text*; handing that to FastStream unparsed sets
    ``text/plain``, and a consumer expecting an object gets a string containing
    one.
    """
    await store_outbox_messages(1)

    await send_worker_command(RelayOutboxCommand())

    [event] = published.all()
    assert event.content_type == "application/json"
    assert isinstance(event.body, dict)


async def test_the_event_type_is_the_routing_key(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """It is how a consumer binds to the events it wants and no others."""
    await store_outbox_messages(2)

    await send_worker_command(RelayOutboxCommand())

    assert set(published.routing_keys()) == {"UserRegistered"}


@inject
async def test_published_messages_stop_being_pending(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    gateway: FromDishka[OutboxCommandGateway],
) -> None:
    """Otherwise the next tick republishes everything, and so does the one after."""
    await store_outbox_messages(3)

    await send_worker_command(RelayOutboxCommand())

    assert await gateway.read_pending(limit=10) == []


async def test_the_batch_size_caps_one_tick(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """A backlog drains over several ticks rather than in one long transaction."""
    await store_outbox_messages(5)

    response = await send_worker_command(RelayOutboxCommand(batch_size=2))

    assert response == RelayOutboxResponse(published=2, total=2)
    assert len(published.all()) == 2


async def test_an_empty_outbox_publishes_nothing(
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """The common case — the relay runs every minute and usually finds nothing."""
    response = await send_worker_command(RelayOutboxCommand())

    assert response == RelayOutboxResponse(published=0, total=0)
    assert published.all() == ()


async def test_messages_are_published_oldest_first(
    store_outbox_messages: OutboxSeeder,
    send_worker_command: CommandSender,
    published: PublishedEvents,
) -> None:
    """A rename published before the registration it followed makes no sense."""
    stored = await store_outbox_messages(4)

    await send_worker_command(RelayOutboxCommand())

    assert [event.message_id for event in published.all()] == [
        str(message.id)
        for message in sorted(stored, key=lambda message: message.created_at)
    ]
