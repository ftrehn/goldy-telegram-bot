"""Taskiq worker entry point.

Run with::

    taskiq worker goldy.worker_app:create_worker_taskiq_app
"""

import logging
from typing import Final

from dishka import AsyncContainer
from dishka.integrations.taskiq import setup_dishka
from faststream.rabbit import RabbitBroker
from sqlalchemy.orm import clear_mappers
from taskiq import AsyncBroker, ScheduleSource, TaskiqEvents, TaskiqState

from goldy.setup.bootstrap.setups.configs_setup import (
    SharedConfigs,
    load_notification_config,
    load_shared_configs,
    make_worker_container_context,
)
from goldy.setup.bootstrap.setups.database_setup import setup_map_tables
from goldy.setup.bootstrap.setups.logging_setup import configure_logging
from goldy.setup.bootstrap.setups.notifications_setup import (
    setup_notification_consumers,
)
from goldy.setup.bootstrap.setups.task_manager_setup import (
    setup_event_broker,
    setup_schedule_source,
    setup_task_manager,
    setup_task_manager_middlewares,
    setup_task_manager_tasks,
)
from goldy.setup.configs.logging_config import LoggingConfig
from goldy.setup.configs.notification_config import NotificationConfig
from goldy.setup.ioc.containers import make_worker_container

logger: Final[logging.Logger] = logging.getLogger(__name__)


def create_worker_taskiq_app() -> AsyncBroker:
    """Builds the broker the worker process serves tasks from.

    A factory rather than module-level assignments: importing this module must
    not open connections or read the environment, or every tool that merely
    imports it — the scheduler, a test, an IDE — pays for a broker it will not
    use.

    Retry middleware is applied here and nowhere else: only the side that
    executes a task can retry it, and the bot never does.

    This process both publishes and consumes on the event broker. The relay
    publishes domain events to the topic exchange on its cron tick, and the
    notification subscribers read them back off it — which is why the broker is
    started rather than merely connected, and why the subscribers are attached
    before that happens.
    """
    configs: SharedConfigs = load_shared_configs()
    notification_config: NotificationConfig = load_notification_config()
    configure_logging(LoggingConfig())

    worker_broker: AsyncBroker = setup_task_manager_middlewares(
        broker=setup_task_manager(configs.taskiq, configs.rabbitmq, configs.redis),
        taskiq_config=configs.taskiq,
    )

    setup_task_manager_tasks(worker_broker)

    schedule_source: ScheduleSource = setup_schedule_source(configs.redis)

    event_broker: RabbitBroker = setup_event_broker(configs.rabbitmq)

    async def startup(state: TaskiqState) -> None:  # ruff: ignore[unused-function-argument]
        setup_map_tables()
        await event_broker.start()
        logger.info("taskiq worker started")

    async def shutdown(state: TaskiqState) -> None:  # ruff: ignore[unused-function-argument]
        await event_broker.stop()
        clear_mappers()
        logger.info("taskiq worker stopped")

    worker_broker.on_event(TaskiqEvents.WORKER_STARTUP)(startup)
    worker_broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)(shutdown)

    container: AsyncContainer = make_worker_container(
        make_worker_container_context(
            configs,
            worker_broker,
            schedule_source,
            event_broker,
            notification_config,
        ),
    )
    setup_dishka(container, broker=worker_broker)

    setup_notification_consumers(event_broker, container)

    return worker_broker
