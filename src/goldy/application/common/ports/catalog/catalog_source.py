from abc import abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Protocol

from goldy.application.common.ports.catalog.catalog_snapshot import (
    CatalogScope,
    CatalogSnapshot,
)


@dataclass(frozen=True, kw_only=True)
class CatalogPull:
    """One complete pass over a catalog source: its batches and what they cover.

    Three things travel together because the sync is correct only when all
    three agree. ``batches`` are imported one by one, each in its own
    transaction, and every one of them carries ``batch_id``. ``scopes`` are
    the parts of the projection this pass covers **completely**, and only
    those are finalised — once, after the last batch was taken in.

    The scopes are declared up front rather than collected from the batches,
    and that is not tidiness. A pass in which no product had a stock row still
    covers stock: every row the projection holds is then stale and has to go.
    Deriving the list from what arrived would skip exactly that sweep, and the
    bot would keep showing stock the site no longer reports.

    ``batches`` is lazy on purpose. A site catalog of several thousand rows is
    read page by page, and a page is imported before the next is requested,
    so the process never holds the whole catalog and a failure on page seven
    leaves pages one to six imported, stamped and unswept — which is safe,
    because nothing is removed until the pass completes.

    Attributes:
        batch_id: The mark every batch of this pass carries, and the one the
            finalisation sweeps by. At most 64 characters, the width of the
            column it is written to.
        scopes: What to finalise after every batch was imported, in order.
        batches: The snapshots to import, all stamped with ``batch_id``. The
            iterator raises ``CatalogSourceError`` when the source fails
            midway, and the caller finalises nothing then.
    """

    batch_id: str
    scopes: tuple[CatalogScope, ...]
    batches: AsyncIterable[CatalogSnapshot]


class CatalogSource(Protocol):
    """Where a full pass over the catalog comes from.

    **The seam of the integration since ADR-0004.** The site tkgoldy.ru is the
    only bridge to 1C, and the bot pulls the catalog from the site's HTTP API
    on a schedule; the RabbitMQ consumer this port once stood aside for was
    cancelled. Two adapters implement it: the site API one the worker runs,
    and the JSON file the seeder reads, which is a pass of one batch.

    Still **not** a dependency of the import handler, and for the reason it
    never was: the handler takes a snapshot, whoever built it. Only the
    processes that own a source bind this port — the worker (the site) and
    the seeder (a file) — and the bot, which has neither, never learns it
    exists.
    """

    @abstractmethod
    async def pull(self) -> CatalogPull:
        """Starts a pass: fixes its batch id and the scopes it covers.

        Whatever the source needs to know before it can promise the scopes —
        the price lists it will send prices for — is read here, so a source
        that cannot be reached fails before anything is imported.

        Raises:
            CatalogSourceError: the source could not be read or understood.
        """
        raise NotImplementedError
