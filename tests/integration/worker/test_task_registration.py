"""What the scheduler can actually fire.

Separate from the relay tests, and synchronous, because nothing here touches the
database or the broker — it asks the broker what was registered on it. A module
of its own rather than a sync test among async ones, so the file needs no
asyncio marker to opt out of.
"""

import pytest
from taskiq import AsyncBroker

from goldy.application.common.ports.task_manager.task_keys import (
    RELAY_OUTBOX_TASK_NAME,
)
from goldy.infrastructure.task_manager.tasks.outbox_tasks import RELAY_CRON

pytestmark = pytest.mark.integration


def test_the_relay_is_registered_under_the_name_the_scheduler_uses(
    taskiq_broker: AsyncBroker,
) -> None:
    """An unregistered name resolves to nothing and raises no alarm.

    ``TaskIQTaskScheduler`` looks the task up by this string; miss it and the
    outbox simply stops draining, with the first symptom being events nobody
    outside the service ever heard about.
    """
    assert RELAY_OUTBOX_TASK_NAME in taskiq_broker.get_all_tasks()


def test_the_relay_carries_a_cron(taskiq_broker: AsyncBroker) -> None:
    """A registered task with no schedule is a task nobody ever fires.

    ``LabelScheduleSource`` reads this label and nothing else does, so an empty
    one is indistinguishable from a working deployment until somebody notices
    the outbox has been full for a day.
    """
    task = taskiq_broker.get_all_tasks()[RELAY_OUTBOX_TASK_NAME]

    assert task.labels["schedule"] == [{"cron": RELAY_CRON}]
