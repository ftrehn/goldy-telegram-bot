from pathlib import Path
from typing import Final

from dishka import Provider, Scope

from goldy.application.commands.catalog.catalog_synchronizer import (
    CatalogSynchronizer,
)
from goldy.application.common.ports.catalog import CatalogSource
from goldy.infrastructure.adapters.catalog.adaptix_catalog_snapshot_mapper import (
    AdaptixCatalogSnapshotMapper,
)
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)
from goldy.infrastructure.adapters.catalog.json_file_catalog_source import (
    JsonFileCatalogSource,
)


def catalog_source_provider() -> Provider:
    """Where the seeder reads its catalog pass from: a JSON file.

    Only the seeder gets this group; the worker binds the same port to the
    site API through ``site_catalog_provider``. ``CatalogSource`` is not a
    collaborator of ``ImportCatalogHandler`` precisely so that the bot never
    learns the port exists: it has no source and nothing bound to read one
    with, and a container that refuses to build is the good outcome of the
    mistake, not a cost.

    The path arrives as request-scoped context rather than as a config, because
    it comes from ``--file`` on the command line and belongs to one run rather
    than to the process. ``seed_catalog`` supplies it when it opens the scope,
    which keeps one value on one route: the entry point parses it, the adapter
    receives it, and nothing in between holds a second copy that could drift.

    ``Path`` is a coarse key anywhere else and an unambiguous one here - this
    container has exactly one file in it.

    The mapper that reads the contract off the decoded document is ``APP``
    scoped: its retort is built once at import time and it holds nothing of
    one run.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.from_context(provides=Path, scope=Scope.REQUEST)
    provider.provide(
        source=AdaptixCatalogSnapshotMapper,
        provides=CatalogSnapshotMapper,
        scope=Scope.APP,
    )
    provider.provide(source=JsonFileCatalogSource, provides=CatalogSource)
    provider.provide(source=CatalogSynchronizer)
    return provider
