from dataclasses import dataclass, field
from typing import Final

from goldy.application.common.mediator.markers import Command
from goldy.application.common.views.outbox import RelayOutboxResponse

DEFAULT_BATCH_SIZE: Final[int] = 100


@dataclass(frozen=True, slots=True)
class RelayOutboxCommand(Command[RelayOutboxResponse]):
    """Drain a batch of pending outbox messages to the broker.

    Dispatched by the scheduler on a cron tick. Safe to run on several worker
    replicas at once — the gateway claims rows with ``SKIP LOCKED``.
    """

    batch_size: int = field(default=DEFAULT_BATCH_SIZE)
