from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from goldy.application.common.ports.catalog.catalog_snapshot import CatalogSnapshot


class CatalogSource(Protocol):
    """Where the seeder gets a catalog snapshot from.

    **A pulling port, and that is a detail of the CLI seeder rather than the
    seam of the integration.** The RabbitMQ consumer that comes next pushes: it
    is handed a message and cannot implement an interface the bot polls, and it
    should not try. Whoever sits down to write that consumer must not spend a
    day folding push into pull, which is why this is said here in as many
    words.

    The seam is ``ImportCatalogCommand(CatalogSnapshot)``. The consumer builds
    the snapshot out of the message itself and sends the command; this port
    never enters that path, and it is deliberately **not** a dependency of the
    import handler — making it one would drag it into the Telegram and worker
    containers, where nothing binds it and neither would build.
    """

    @abstractmethod
    async def read_snapshot(self) -> CatalogSnapshot:
        """The batch this source has to offer.

        Raises:
            CatalogSourceError: the source could not be read or understood.
        """
        raise NotImplementedError
