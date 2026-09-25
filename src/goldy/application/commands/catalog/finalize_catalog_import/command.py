from dataclasses import dataclass

from goldy.application.common.mediator.markers import Command
from goldy.application.common.ports.catalog import CatalogScope
from goldy.application.common.views.catalog import CatalogFinalizationResponse


@dataclass(frozen=True, slots=True)
class FinalizeCatalogImportCommand(Command[CatalogFinalizationResponse]):
    """Removes whatever the named batch did not mention, within its scope.

    Separate from the import itself because the two answer different
    questions. ``ImportCatalogCommand`` says "here is some data", which may be
    one chunk of many; this one says "that was all of it", which only the
    sender knows — ``CatalogSynchronizer``, once the whole pass of the site
    (or the seeder's single batch) went in.

    The scope is not decoration. "Whatever was not mentioned is gone" holds
    only inside the part of the projection the batch was about: exporting one
    price list without it would delete every other one.
    """

    batch_id: str
    scope: CatalogScope
