import logging
from typing import Final

from dishka import FromDishka
from dishka.integrations.taskiq import inject
from taskiq import AsyncBroker

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)
from goldy.application.common.ports.task_manager.task_keys import (
    SYNC_CATALOG_TASK_NAME,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

MAX_RETRIES: Final[int] = 2
RETRY_DELAY_SECONDS: Final[int] = 60
"""Two more attempts a minute apart, then wait for the next tick.

A pass that failed leaves nothing half-swept — finalisation runs only after
the last page — so there is no urgency to retry harder. Overlap is not this
policy's job: ``CatalogSyncLock`` lets one pass run at a time, and a retry that
lands while another pass is running is skipped rather than raised.
"""


@inject(patch_module=True)
async def sync_catalog_task(synchronizer: FromDishka[CatalogSynchronizer]) -> None:
    """Pulls the whole catalog from the site and replaces the projection's.

    ADR-0004: the site is the only bridge to 1C, and the bot pulls rather than
    being pushed to — it has no public address to be pushed to. The pass
    imports batch by batch and finalises only after all of them; a failure on
    the way raises, taskiq retries, and the projection keeps what it had.

    A pass that finds another one running returns quietly: the synchronizer
    has logged it, and raising would turn one skipped tick into a retry storm
    against the pass that is doing the work.
    """
    await synchronizer.run()


def setup_catalog_tasks(broker: AsyncBroker, cron: str) -> None:
    """Registers the catalog pull on the broker, on the configured schedule.

    The cron is passed in as a string rather than read from a config: this
    module is infrastructure, and the setting belongs to the composition root.
    """
    broker.register_task(
        func=sync_catalog_task,
        task_name=SYNC_CATALOG_TASK_NAME,
        schedule=[{"cron": cron}],
        retry_on_error=True,
        max_retries=MAX_RETRIES,
        delay=RETRY_DELAY_SECONDS,
    )
