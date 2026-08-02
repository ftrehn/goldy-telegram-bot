import logging
from typing import Final

from dishka import FromDishka
from dishka.integrations.taskiq import inject
from taskiq import AsyncBroker

from goldy.application.commands.outbox.relay_outbox.command import RelayOutboxCommand
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.task_manager.task_keys import (
    RELAY_OUTBOX_TASK_NAME,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

RELAY_CRON: Final[str] = "* * * * *"
"""Every minute.

The tick is the delay a domain event waits before anyone outside the service
hears about it, so it wants to be short. It cannot be much shorter than this
either: taskiq's cron granularity is a minute.
"""

MAX_RETRIES: Final[int] = 3
RETRY_DELAY_SECONDS: Final[int] = 15


@inject(patch_module=True)
async def relay_outbox_task(sender: FromDishka[Sender]) -> None:
    """Drains a batch of pending outbox messages, once a minute.

    Safe to retry and safe to run on several replicas: the gateway claims rows
    with ``SKIP LOCKED``, and a message is marked processed only after the
    transport accepted it.

    Dispatches through ``Sender`` rather than calling the handler, because the
    transaction that holds those row locks is opened by the pipeline — a direct
    call would release them before ``mark_processed`` committed.
    """
    response = await sender.send(RelayOutboxCommand())

    if response.total:
        logger.info(
            "relay_outbox: published %d of %d",
            response.published,
            response.total,
        )


def setup_outbox_tasks(broker: AsyncBroker) -> None:
    """Registers the relay on the broker, with its schedule attached.

    ``register_task`` rather than the decorator: the decorator binds to whatever
    broker happens to be default at import time, and this module is imported by
    the scheduler process too — which builds its own.
    """
    broker.register_task(
        func=relay_outbox_task,
        task_name=RELAY_OUTBOX_TASK_NAME,
        schedule=[{"cron": RELAY_CRON}],
        retry_on_error=True,
        max_retries=MAX_RETRIES,
        delay=RETRY_DELAY_SECONDS,
    )
