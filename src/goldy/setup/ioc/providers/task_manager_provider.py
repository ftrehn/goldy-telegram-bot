from typing import Final

from dishka import Provider, Scope
from faststream.rabbit import RabbitBroker
from taskiq import AsyncBroker, ScheduleSource

from goldy.application.common.ports.outbox import OutboxPublisher
from goldy.application.common.ports.task_manager.task_manager import TaskScheduler
from goldy.infrastructure.adapters.outbox.faststream_outbox_publisher import (
    FastStreamOutboxPublisher,
)
from goldy.infrastructure.task_manager.task_iq_task_manager import TaskIQTaskScheduler


def task_manager_provider() -> Provider:
    """The broker side of the world, for processes that actually have one.

    The broker and its schedule source come from the context: both are created
    before the container, because registering tasks on a broker is what makes
    it usable and that has to happen at import time for the taskiq CLI to find
    them.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.from_context(provides=AsyncBroker, scope=Scope.APP)
    provider.from_context(provides=ScheduleSource, scope=Scope.APP)
    # FastStream's own connection, not taskiq's: the relay publishes domain
    # events to a topic exchange consumers bind to, which is a different thing
    # from the work queue taskiq owns.
    provider.from_context(provides=RabbitBroker, scope=Scope.APP)
    provider.provide(source=TaskIQTaskScheduler, provides=TaskScheduler)
    provider.provide(source=FastStreamOutboxPublisher, provides=OutboxPublisher)
    return provider
