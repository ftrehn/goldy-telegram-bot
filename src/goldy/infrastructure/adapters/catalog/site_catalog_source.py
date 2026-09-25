import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Final, override
from uuid import uuid7

from goldy.application.common.ports.catalog import (
    CatalogPull,
    CatalogScope,
    CatalogScopeKind,
    CatalogSnapshot,
    CatalogSource,
    CategoryRow,
    PriceRow,
    PriceTypeRow,
)
from goldy.infrastructure.adapters.catalog.site_catalog_documents import (
    STOCK_WAREHOUSE_ID,
    ItemReader,
    ItemRows,
    read_price_types,
    read_sections,
)
from goldy.infrastructure.adapters.site_api.site_api_client import SiteApiClient
from goldy.infrastructure.errors import (
    CatalogSourceReadError,
    CatalogSourceUnavailableError,
    SiteApiError,
    SiteApiUnavailableError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

SECTIONS_PATH: Final[str] = "catalog/sections"
PRICE_TYPES_PATH: Final[str] = "catalog/price-types"
ITEMS_PATH: Final[str] = "catalog/items"


class SiteCatalogSource(CatalogSource):
    """Pulls the whole guest catalog from the site API, one pass per call.

    ADR-0004 in one class. The site is the only bridge to 1C, it already
    applies every rule of visibility and price the storefront applies, and it
    hands the catalog out as a guest sees it: sections in one piece, price
    types, then items page by page. This adapter turns that into a
    :class:`CatalogPull`:

    - **One batch id for the pass**, a fresh time-ordered UUID, stamped on
      every batch. The site has no change stamps a projection could trust, so
      rows carry no ``source_changed_at`` and every pass simply wins; what
      ends a row's life is not appearing in a completed pass.
    - **Scopes declared before the first item is read** — categories,
      products, price types, prices under each announced price list, and
      stock at warehouse ``'*'``. Price type bindings are not among them: the
      site does not send them (personal prices come from the site per
      customer, later), and a sweep here would delete whatever the seeder's
      fixture put there.
    - **Batches split by kind.** Each page of items becomes up to three
      snapshots — products, prices per price list, stock — so each import's
      log line counts one thing. A page is at most the configured page size
      (the site allows 1000), which keeps one INSERT under Postgres's limit of
      32 767 bind parameters with room to spare.

    Categories and price types are read inside :meth:`pull`, before anything
    is imported: an unreachable site then fails the pass at once, and the
    price lists are known in time to declare their scopes.

    A pass that turns up no sections, no price types or no items at all is
    refused rather than finalised. Every one of those is far likelier to be a
    fault on the site than an empty shop, and finalising it would deactivate
    the whole catalog in the bot.

    Every :class:`SiteApiError` is re-raised as the port's own error:
    :class:`CatalogSourceUnavailableError` for what a later attempt may get
    past, :class:`CatalogSourceReadError` for everything else.
    """

    def __init__(self, client: SiteApiClient, page_size: int) -> None:
        self._client: Final[SiteApiClient] = client
        self._page_size: Final[int] = page_size

    @override
    async def pull(self) -> CatalogPull:
        batch_id = f"site-{uuid7()}"

        with _translated():
            sections = await self._client.get(SECTIONS_PATH)
            price_types_page = await self._client.get(PRICE_TYPES_PATH)

        categories = read_sections(sections.data)
        price_types = read_price_types(price_types_page.data)

        if not categories:
            msg = "The site sent no catalog sections; refusing to sweep the catalog."
            raise CatalogSourceReadError(msg)

        if not price_types:
            msg = "The site sent no price types; refusing to sweep the catalog."
            raise CatalogSourceReadError(msg)

        scopes = (
            CatalogScope(kind=CatalogScopeKind.CATEGORIES),
            CatalogScope(kind=CatalogScopeKind.PRODUCTS),
            CatalogScope(kind=CatalogScopeKind.PRICE_TYPES),
            *(
                CatalogScope(kind=CatalogScopeKind.PRICES, price_type_id=row.id)
                for row in price_types
            ),
            CatalogScope(kind=CatalogScopeKind.STOCK, warehouse_id=STOCK_WAREHOUSE_ID),
        )

        logger.info(
            "site catalog: pass %s started, sections=%d price_types=%d",
            batch_id,
            len(categories),
            len(price_types),
        )

        return CatalogPull(
            batch_id=batch_id,
            scopes=scopes,
            batches=self._batches(batch_id, categories, price_types),
        )

    async def _batches(
        self,
        batch_id: str,
        categories: tuple[CategoryRow, ...],
        price_types: tuple[PriceTypeRow, ...],
    ) -> AsyncIterator[CatalogSnapshot]:
        """The pass's snapshots: the tree, the price lists, then every page.

        Raises:
            CatalogSourceError: a page failed, or the pass held no items.
        """
        yield CatalogSnapshot(
            batch_id=batch_id,
            scope=CatalogScope(kind=CatalogScopeKind.CATEGORIES),
            categories=categories,
        )
        yield CatalogSnapshot(
            batch_id=batch_id,
            scope=CatalogScope(kind=CatalogScopeKind.PRICE_TYPES),
            price_types=price_types,
        )

        reader = ItemReader(price_type_ids=frozenset(row.id for row in price_types))
        pages = self._client.paginate(ITEMS_PATH, limit=self._page_size)
        items = skipped = 0

        while True:
            with _translated():
                page = await anext(pages, None)

            if page is None:
                break

            rows = reader.read_page(page.data)
            items += len(rows.products)
            skipped += rows.skipped

            for snapshot in _page_snapshots(batch_id, rows):
                yield snapshot

        if not items:
            msg = "The site sent no catalog items; refusing to sweep the catalog."
            raise CatalogSourceReadError(msg)

        logger.info(
            "site catalog: pass %s read, items=%d skipped=%d",
            batch_id,
            items,
            skipped,
        )


def _page_snapshots(batch_id: str, rows: ItemRows) -> Iterator[CatalogSnapshot]:
    """Up to one snapshot per kind for a page, leaving out the empty kinds.

    Prices are split by price list so each snapshot's scope says exactly what
    it holds; today the site sends one list, and the split costs nothing.
    """
    if rows.products:
        yield CatalogSnapshot(
            batch_id=batch_id,
            scope=CatalogScope(kind=CatalogScopeKind.PRODUCTS),
            products=rows.products,
        )

    by_price_type: dict[str, list[PriceRow]] = {}
    for price in rows.prices:
        by_price_type.setdefault(price.price_type_id, []).append(price)

    for price_type_id, prices in by_price_type.items():
        yield CatalogSnapshot(
            batch_id=batch_id,
            scope=CatalogScope(kind=CatalogScopeKind.PRICES, price_type_id=price_type_id),
            prices=tuple(prices),
        )

    if rows.stock:
        yield CatalogSnapshot(
            batch_id=batch_id,
            scope=CatalogScope(
                kind=CatalogScopeKind.STOCK, warehouse_id=STOCK_WAREHOUSE_ID
            ),
            stock=rows.stock,
        )


@contextmanager
def _translated() -> Iterator[None]:
    """Turns a site API failure into the error ``CatalogSource`` promises.

    Raises:
        CatalogSourceUnavailableError: the site did not answer, or said "not
            now" — a later pass may well succeed.
        CatalogSourceReadError: the site refused the request or answered with
            something that is not the contract.
    """
    try:
        yield
    except SiteApiUnavailableError as e:
        msg = f"The site catalog is unavailable: {e}"
        raise CatalogSourceUnavailableError(msg) from e
    except SiteApiError as e:
        msg = f"The site catalog could not be read: {e}"
        raise CatalogSourceReadError(msg) from e
