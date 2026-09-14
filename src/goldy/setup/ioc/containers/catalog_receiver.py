from collections.abc import Iterable
from typing import Final

from dishka import AsyncContainer, Provider, make_async_container

from goldy.setup.ioc.containers.common import common_providers
from goldy.setup.ioc.providers import catalog_snapshot_mapper_provider


def catalog_receiver_providers() -> Iterable[Provider]:
    """The shared core plus one reading of the snapshot contract.

    The receiver is the seeder with the file taken away. 1C posts the same
    documents the seeder reads off disk, so the mapper is shared; the file
    source is not, because there is no file, and a container that could
    resolve a ``CatalogSource`` here would be promising a path nobody
    supplies.

    Nothing interactive and nothing from taskiq, for the reasons the seeder
    gives. A batch from 1C is nobody's request, so a handler that needs to
    know who is asking must fail to resolve at startup; and the receiver
    answers 1C inside the HTTP request, so it has no broker to enqueue
    anything on and no schedule to keep. Adding either group would make this
    container able to do something the process it serves must not.
    """
    return (
        *common_providers(),
        catalog_snapshot_mapper_provider(),
    )


def make_catalog_receiver_container(context: dict[type, object]) -> AsyncContainer:
    """Builds the container the catalog receiver runs on.

    *context* carries the loaded configs, the receiver's own included. The
    aiohttp application is built on top of this container rather than inside
    it: dishka's aiohttp integration opens a request scope per HTTP request,
    and the handlers resolve the mediator and the mapper from that scope.
    """
    providers: Final[Iterable[Provider]] = tuple(catalog_receiver_providers())
    return make_async_container(*providers, context=context)
