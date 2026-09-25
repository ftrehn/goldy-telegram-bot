import logging
from dataclasses import dataclass
from typing import Final

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.common.mediator.sender import Sender
from goldy.application.common.ports.catalog import CatalogSource, CatalogSyncLock
from goldy.application.error import CatalogSnapshotError

logger: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogSyncReport:
    """What one pass did, in the numbers a log line and a test both want.

    Attributes:
        batch_id: The pass, as the projection's rows are stamped with it.
        batches: How many snapshots were imported, each its own transaction.
        accepted: Rows the projection took in, summed over every batch.
        discarded: Price rows refused before a customer could see them.
        swept: Rows the finalisations deactivated or deleted, over all scopes.
    """

    batch_id: str
    batches: int
    accepted: int
    discarded: int
    swept: int


class CatalogSynchronizer:
    """Runs one pass of a catalog source through the two import commands.

    **Every batch first, the sweeps last, and the sweeps only if every batch
    made it.** Each import is its own transaction, so a failure on the seventh
    page leaves six pages imported and stamped; that is harmless, because an
    upsert removes nothing. What must not happen is a finalisation after a
    partial pass — it would deactivate every product the missing pages held
    and delete their prices. So nothing here catches: the error the source or
    a command raised leaves this method, no sweep runs, and the next pass
    restamps the same rows with a batch id of its own.

    Not a command, and deliberately not one. A handler that sent these commands
    would nest their transactions inside its own, and the point is the
    opposite — one transaction per batch, committed as it goes, so a catalog of
    thousands of rows never sits in one transaction. That is also why it takes
    ``Sender`` rather than the handlers: each command still goes through the
    transaction and events pipelines like any other.

    **One pass at a time, across every process.** Two overlapping passes
    finalise by different batch ids, and the first to finish sweeps the rows
    the other has just restamped. The whole pass therefore runs inside
    ``CatalogSyncLock``; a pass that finds the lock taken logs, returns
    ``None`` and does nothing — the running pass brings the same catalog, and
    raising would only feed taskiq's retries into the next collision.

    Shared by the worker's scheduled pull and the seeder's file, which is what
    keeps the file path an honest rehearsal of the real one. It lives next to
    the commands it sends because both of its callers are allowed to reach
    ``application.commands`` and nothing else in between should.
    """

    def __init__(
        self,
        catalog_source: CatalogSource,
        sender: Sender,
        catalog_sync_lock: CatalogSyncLock,
    ) -> None:
        self._catalog_source: Final[CatalogSource] = catalog_source
        self._sender: Final[Sender] = sender
        self._lock: Final[CatalogSyncLock] = catalog_sync_lock

    async def run(self) -> CatalogSyncReport | None:
        """Runs one pass under the lock, or nothing if another pass holds it.

        Returns:
            The report of the pass, or ``None`` when it was skipped because
            another pass is running.

        Raises:
            AppError: the lock could not be asked for; no pass ran.
            CatalogSourceError: see :meth:`_run`.
            CatalogSnapshotError: see :meth:`_run`.
        """
        async with self._lock.hold() as acquired:
            if not acquired:
                logger.info("catalog_sync: another pass is running, this one skipped")
                return None

            return await self._run()

    async def _run(self) -> CatalogSyncReport:
        """Imports every batch of one pass, then finalises the scopes it covers.

        Raises:
            CatalogSourceError: the source failed before or during the pass;
                nothing was finalised.
            CatalogSnapshotError: a batch carried a different batch id than
                the pass it belongs to, or a finalisation left the projection
                without its default price type (and was rolled back).
        """
        pull = await self._catalog_source.pull()

        batches = accepted = discarded = 0
        async for snapshot in pull.batches:
            if snapshot.batch_id != pull.batch_id:
                msg = (
                    f"A batch of pass '{pull.batch_id}' is stamped "
                    f"'{snapshot.batch_id}'; refusing to finalise a mixed pass."
                )
                raise CatalogSnapshotError(msg)

            imported = await self._sender.send(ImportCatalogCommand(snapshot=snapshot))
            batches += 1
            accepted += imported.accepted
            discarded += imported.discarded

        swept = 0
        for scope in pull.scopes:
            finalized = await self._sender.send(
                FinalizeCatalogImportCommand(batch_id=pull.batch_id, scope=scope),
            )
            swept += finalized.swept

        report = CatalogSyncReport(
            batch_id=pull.batch_id,
            batches=batches,
            accepted=accepted,
            discarded=discarded,
            swept=swept,
        )
        logger.info(
            "catalog_sync: batch=%s batches=%d accepted=%d discarded=%d swept=%d",
            report.batch_id,
            report.batches,
            report.accepted,
            report.discarded,
            report.swept,
        )
        return report
