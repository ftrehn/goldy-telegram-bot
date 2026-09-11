from pathlib import Path
from typing import Final

from dishka import Provider, Scope

from goldy.application.common.ports.catalog import CatalogSource
from goldy.infrastructure.adapters.catalog.json_file_catalog_source import (
    JsonFileCatalogSource,
)


def catalog_source_provider() -> Provider:
    """Where a catalog snapshot is read from, for the one process that reads one.

    Only the seeder gets this group. ``CatalogSource`` is not a collaborator of
    ``ImportCatalogHandler`` precisely so that the bot and the worker never
    learn the port exists: they have no file to read and nothing bound to read
    it with, and a container that refuses to build is the good outcome of the
    mistake, not a cost.

    The path arrives as request-scoped context rather than as a config, because
    it comes from ``--file`` on the command line and belongs to one run rather
    than to the process. ``seed_catalog`` supplies it when it opens the scope,
    which keeps one value on one route: the entry point parses it, the adapter
    receives it, and nothing in between holds a second copy that could drift.

    ``Path`` is a coarse key anywhere else and an unambiguous one here - this
    container has exactly one file in it.
    """
    provider: Final[Provider] = Provider(scope=Scope.REQUEST)
    provider.from_context(provides=Path, scope=Scope.REQUEST)
    provider.provide(source=JsonFileCatalogSource, provides=CatalogSource)
    return provider
