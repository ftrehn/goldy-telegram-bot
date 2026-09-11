from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.ports.catalog import CatalogSnapshot
from goldy.application.common.views.catalog import CatalogImportResponse


@dataclass(frozen=True, slots=True)
class ImportCatalogCommand(Command[CatalogImportResponse]):
    """Takes one batch of catalog data into the projection.

    **This command is the seam of the integration**, and the snapshot is built
    by whoever sends it. The CLI seeder reads one from a file through
    ``CatalogSource``; the RabbitMQ consumer that comes later builds one out of
    a message it was handed. Neither of them is a dependency of the handler,
    which is what lets the same command serve a puller and a pusher.

    A **batch**, never the whole catalog. 1C sends its nomenclature in parts
    and exports prices and stock separately from the reference itself, so
    "whatever is not in here is gone" is not true of a single call and sweeping
    is a separate command. What this one does is upsert and stamp the batch.
    """

    snapshot: CatalogSnapshot
