import logging
from pathlib import Path
from typing import Final

from dishka import AsyncContainer, Scope

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.catalog import CatalogSource

logger: Final[logging.Logger] = logging.getLogger(__name__)


async def seed_catalog(container: AsyncContainer, path: Path) -> None:
    """Fills the catalog projection from a file, in two commands.

    Opens a request scope by hand for the reason ``seed_admins`` does: there is
    no update to hang one off, and the commands still need a session and a
    transaction like any other. The path enters the scope as context, which is
    how the source adapter receives it without the port promising a file.

    Two sends rather than one, and in this order. The import takes the batch in
    and stamps it; the finalisation says "that was all of it" and sweeps what
    the batch did not mention. A seeder reading a whole file could in principle
    do both at once, but the consumer that replaces it cannot — 1C sends its
    nomenclature in parts — and having the seeder use the same two commands is
    what keeps the second path exercised before it exists.

    Lives in bootstrap rather than in the entry point so the entry point stays
    an orchestration script. ``setup`` is one of the few packages import-linter
    lets reach into ``application.commands``; ``goldy.catalog_seed_app`` is not,
    and that is enforced rather than agreed.
    """
    async with container(context={Path: path}, scope=Scope.REQUEST) as request_scope:
        source = await request_scope.get(CatalogSource)
        sender = await request_scope.get(Sender)

        snapshot = await source.read_snapshot()

        imported = await sender.send(ImportCatalogCommand(snapshot=snapshot))
        finalized = await sender.send(
            FinalizeCatalogImportCommand(
                batch_id=snapshot.batch_id,
                scope=snapshot.scope,
            ),
        )

    logger.info(
        "seed_catalog: batch=%s scope=%s accepted=%d discarded=%d swept=%d",
        imported.batch_id,
        imported.scope,
        imported.accepted,
        imported.discarded,
        finalized.swept,
    )
