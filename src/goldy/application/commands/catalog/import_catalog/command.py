from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.ports.catalog import CatalogSnapshot
from goldy.application.common.views.catalog import CatalogImportResponse


@dataclass(frozen=True, slots=True)
class ImportCatalogCommand(Command[CatalogImportResponse]):
    """Takes one batch of catalog data into the projection.

    The snapshot is built by whoever sends it: ``CatalogSynchronizer`` hands
    over each batch of a ``CatalogPull`` — a page of the site's catalog in the
    worker, the whole file in the seeder (ADR-0004). The source is not a
    dependency of the handler, which is what keeps this command resolvable in
    every container.

    A **batch**, never the whole catalog. The site is read page by page and
    each page is split by kind, so "whatever is not in here is gone" is not
    true of a single call and sweeping is a separate command. What this one
    does is upsert and stamp the batch.
    """

    snapshot: CatalogSnapshot
