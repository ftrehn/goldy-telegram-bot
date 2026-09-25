import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final, override

from goldy.application.common.ports.catalog import (
    CatalogPull,
    CatalogSnapshot,
    CatalogSource,
)
from goldy.infrastructure.adapters.catalog.catalog_snapshot_mapper import (
    CatalogSnapshotMapper,
)
from goldy.infrastructure.errors import CatalogSourceReadError

logger: Final[logging.Logger] = logging.getLogger(__name__)


class JsonFileCatalogSource(CatalogSource):
    """Reads one catalog batch out of a JSON file.

    The seeder's source and nothing more. The worker pulls the real catalog
    from the site API through the same port (ADR-0004); a file is a pass of
    exactly one batch, finalised over the one scope the file names.

    Two jobs, and only the first is this class's own: getting text off the
    disk and decoding it as JSON. Whether what came out is a snapshot is the
    mapper's question, injected through the constructor so the HTTP receiver
    that could come later asks the same one of a request body — and so the reading
    of the contract can change without this file changing.

    The path arrives in the constructor as request-scoped context, because it
    comes from ``--file`` on the command line and belongs to one run rather
    than to the process. A config would make it a property of the bot, and the
    bot never reads a catalog file.

    Every failure of the file and of its shape leaves here as
    :class:`CatalogSourceReadError`, naming the field that was wrong. A seeder
    is run by a person watching the output, and "products[7].name: expected a
    string" is the difference between fixing a fixture and guessing at it.
    """

    def __init__(
        self,
        path: Path,
        catalog_snapshot_mapper: CatalogSnapshotMapper,
    ) -> None:
        self._path: Final[Path] = path
        self._mapper: Final[CatalogSnapshotMapper] = catalog_snapshot_mapper

    @override
    async def pull(self) -> CatalogPull:
        """The file as a pass of one batch, swept over the scope it names.

        The file is read here rather than lazily, so a missing or malformed
        fixture fails before anything is imported — the port promises that of
        every source.
        """
        snapshot = await self.read_snapshot()
        return CatalogPull(
            batch_id=snapshot.batch_id,
            scopes=(snapshot.scope,),
            batches=_one(snapshot),
        )

    async def read_snapshot(self) -> CatalogSnapshot:
        """The one batch the file holds.

        Raises:
            CatalogSourceReadError: the file cannot be read, is not JSON, or
                is not shaped like a snapshot.
        """
        snapshot = self._mapper.to_snapshot(_parse(await self._read()))

        logger.info(
            "json_file_catalog_source: file=%s batch=%s categories=%d products=%d",
            self._path,
            snapshot.batch_id,
            len(snapshot.categories),
            len(snapshot.products),
        )

        return snapshot

    async def _read(self) -> str:
        """Reads the file off the event loop, since a fixture can be large.

        Raises:
            CatalogSourceReadError: the file is missing, unreadable, or not
                text this service can decode.
        """
        try:
            return await asyncio.to_thread(self._path.read_text, encoding="utf-8")
        except OSError as e:
            logger.exception("failed to read the catalog file")
            msg = f"Cannot read the catalog snapshot at '{self._path}'."
            raise CatalogSourceReadError(msg) from e
        except UnicodeDecodeError as e:
            logger.exception("failed to decode the catalog file")
            msg = f"The catalog snapshot at '{self._path}' is not valid UTF-8."
            raise CatalogSourceReadError(msg) from e


async def _one(snapshot: CatalogSnapshot) -> AsyncIterator[CatalogSnapshot]:
    """The single batch of a file, as the stream ``CatalogPull`` carries."""
    yield snapshot


def _parse(text: str) -> object:
    """Turns the text of the file into whatever JSON it spells.

    Raises:
        CatalogSourceReadError: the file is not JSON at all.
    """
    try:
        return json.loads(text)
    except ValueError as e:
        msg = f"The catalog snapshot is not valid JSON: {e}."
        raise CatalogSourceReadError(msg) from e
