import logging
from typing import Final

from dishka import FromDishka
from dishka.integrations.taskiq import inject
from taskiq import AsyncBroker

from goldy.application.commands.site.order_handover_runner import OrderHandoverRunner
from goldy.application.common.ports.task_manager.task_keys import (
    HAND_OVER_ORDERS_TASK_NAME,
    PULL_SITE_ORDER_STATUSES_TASK_NAME,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

HAND_OVER_CRON: Final[str] = "* * * * *"
"""Every minute — how long a new order waits before the site has it.

Taskiq's cron cannot go finer, and there is no reason to want it: the order
is already with the bot's managers the moment it is placed.
"""

PULL_STATUSES_CRON: Final[str] = "*/2 * * * *"
"""Every two minutes — how late a customer hears the site moved their order."""


@inject(patch_module=True)
async def hand_over_orders_task(runner: FromDishka[OrderHandoverRunner]) -> None:
    """Hands the due orders from the queue to the site (ADR-0004).

    Not retried by taskiq: an order the site did not take is already
    rescheduled by its own record, with a growing delay, and a task-level
    retry would only hit the site again at once.
    """
    await runner.hand_over_due()


@inject(patch_module=True)
async def pull_site_order_statuses_task(runner: FromDishka[OrderHandoverRunner]) -> None:
    """Reads the site's order feed and moves the bot's orders to match.

    Not retried either: the next tick starts from the same watermark, so a
    failed pass loses nothing but two minutes.
    """
    await runner.pull_statuses()


def setup_site_order_tasks(broker: AsyncBroker) -> None:
    """Registers the handover and the status feed on the broker, with schedules."""
    broker.register_task(
        func=hand_over_orders_task,
        task_name=HAND_OVER_ORDERS_TASK_NAME,
        schedule=[{"cron": HAND_OVER_CRON}],
    )
    broker.register_task(
        func=pull_site_order_statuses_task,
        task_name=PULL_SITE_ORDER_STATUSES_TASK_NAME,
        schedule=[{"cron": PULL_STATUSES_CRON}],
    )
