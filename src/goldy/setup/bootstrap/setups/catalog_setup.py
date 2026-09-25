import logging
from pathlib import Path
from typing import Final

from dishka import AsyncContainer, Scope

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def seed_catalog(container: AsyncContainer, path: Path) -> None:
    """Fills the catalog projection from a file, the way the worker syncs it.

    Opens a request scope by hand for the reason ``seed_admins`` does: there is
    no update to hang one off, and the commands still need a session and a
    transaction like any other. The path enters the scope as context, which is
    how the source adapter receives it without the port promising a file.

    The run itself is :class:`CatalogSynchronizer`, the same one the worker's
    scheduled pull from the site goes through: the file is a pass of one batch,
    imported and then finalised over the scope it names. Sharing it is what
    keeps the seeder an honest rehearsal of the real path rather than a second
    implementation of it.

    Lives in bootstrap rather than in the entry point so the entry point stays
    an orchestration script. ``setup`` is one of the few packages import-linter
    lets reach into ``application.commands``; ``goldy.catalog_seed_app`` is not,
    and that is enforced rather than agreed.
    """
    async with container(context={Path: path}, scope=Scope.REQUEST) as request_scope:
        synchronizer = await request_scope.get(CatalogSynchronizer)
        report = await synchronizer.run()

    logger.info(
        "seed_catalog: file=%s batch=%s accepted=%d discarded=%d swept=%d",
        path,
        report.batch_id,
        report.accepted,
        report.discarded,
        report.swept,
    )
