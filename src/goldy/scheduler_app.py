"""Taskiq scheduler entry point.

Run with::

    taskiq scheduler goldy.scheduler_app:create_scheduler_taskiq_app
"""

import logging
from typing import Final

from taskiq import AsyncBroker, ScheduleSource, TaskiqScheduler

from goldy.setup.bootstrap.setups.configs_setup import load_shared_configs
from goldy.setup.bootstrap.setups.task_manager_setup import (
    setup_schedule_source,
    setup_scheduler,
)
from goldy.worker_app import create_worker_taskiq_app

logger: Final[logging.Logger] = logging.getLogger(__name__)


def create_scheduler_taskiq_app() -> TaskiqScheduler:
    """Builds the scheduler that fires the outbox relay on a tick.

    Reuses the worker's broker so both sides agree on queue naming and
    transport; a separately built one could drift and then fire into a queue
    nobody consumes — which looks exactly like the outbox quietly not draining.

    The scheduler only enqueues. The worker process still does the work, which
    is why both can be scaled apart.
    """
    configs = load_shared_configs()
    worker_broker: AsyncBroker = create_worker_taskiq_app()
    schedule_source: ScheduleSource = setup_schedule_source(configs.redis)

    return setup_scheduler(broker=worker_broker, schedule_source=schedule_source)
