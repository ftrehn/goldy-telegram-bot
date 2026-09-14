from typing import Final

from dishka import Provider, Scope

from goldy.infrastructure.adapters.catalog.adaptix_catalog_snapshot_mapper import (
    AdaptixCatalogSnapshotMapper,
)
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)


def catalog_snapshot_mapper_provider() -> Provider:
    """One reading of the snapshot contract, for both processes that read one.

    Its own group rather than a line in ``catalog_source_provider``, because
    the two things that need it need different company. The seeder reads a
    file, so it takes this together with the file source; the receiver reads
    request bodies 1C posts, and has no file, no path and no ``CatalogSource``
    — a container that could resolve one there would be promising a file that
    does not exist. Splitting the mapper out is what lets the receiver's
    container hold exactly the mapper and nothing that expects a file.

    ``APP`` scoped: the retort behind the mapper is built once at import time
    and holds nothing of one run, so one instance serves every batch the
    process ever sees.
    """
    provider: Final[Provider] = Provider(scope=Scope.APP)
    provider.provide(
        source=AdaptixCatalogSnapshotMapper,
        provides=CatalogSnapshotMapper,
    )
    return provider
