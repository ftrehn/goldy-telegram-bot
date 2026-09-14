from collections.abc import Iterable
from typing import Final

from dishka import AsyncContainer, Provider, make_async_container

from goldy.setup.ioc.containers.common import common_providers
from goldy.setup.ioc.providers import catalog_source_provider


def catalog_seed_providers() -> Iterable[Provider]:
    """The shared core plus the one file the seeder reads.

    Neither existing container fits, and the reasons are different. The
    Telegram one asks for a ``Bot`` in its context, which a command-line script
    has no business creating; the worker one drags in taskiq, a broker and a
    schedule source to run a job that talks to nothing but Postgres.

    No interactive providers, and that is the point of the split: seeding the
    catalog is nobody's request, so this container must refuse to resolve
    anything that expects a customer. If a handler ever appears here that needs
    one, this is where it shows up.
    """
    return (
        *common_providers(),
        catalog_source_provider(),
    )


def make_catalog_seed_container(context: dict[type, object]) -> AsyncContainer:
    """Builds the container the catalog seeder runs on.

    *context* carries the loaded configs, exactly as it does for the other
    processes. The path to the snapshot is not among them: it belongs to one
    run rather than to the process, so ``seed_catalog`` contributes it when it
    opens the request scope.
    """
    providers: Final[Iterable[Provider]] = tuple(catalog_seed_providers())
    return make_async_container(*providers, context=context)
