import logging
from decimal import Decimal
from typing import Final, override

from goldy.application.commands.catalog.import_catalog.command import (
    ImportCatalogCommand,
)
from goldy.application.commands.catalog.scope_description import describe_scope
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.catalog import CatalogProjectionDao
from goldy.application.common.views.catalog import CatalogImportResponse
from goldy.domain.common.values.currency import Currency

logger: Final[logging.Logger] = logging.getLogger(__name__)

SUPPORTED_CURRENCIES: Final[frozenset[str]] = frozenset(
    currency.value for currency in Currency
)


class ImportCatalogHandler(CommandHandler[ImportCatalogCommand, CatalogImportResponse]):
    """Upserts one batch into the projection and stamps it with its batch id.

    Nothing is removed here. The stamp is what the finalisation command selects
    by afterwards, and keeping the two apart is what lets 1C send its
    nomenclature in parts: a single call meaning "this is the catalog now"
    would let the second part erase the first.

    Every collection the snapshot carries is written, regardless of its scope.
    The scope says what a later sweep may remove, not what a batch is allowed
    to contain — the file the seeder reads carries the whole catalog at once,
    while a batch 1C posts carries one kind, and both are the same call here.

    Two kinds of price row are refused before a customer can see them, and both
    are counted rather than logged and forgotten. A price of zero reads as
    "free" on a storefront, and ``Money`` would happily carry it all the way
    into an order line; a price in a currency this service does not know would
    be shown as roubles, which is worse than refusing it. Neither is an
    exception: one bad row in an export of thousands must not cost the shop its
    whole catalog.
    """

    def __init__(self, catalog_projection_dao: CatalogProjectionDao) -> None:
        self._catalog_projection_dao: Final[CatalogProjectionDao] = catalog_projection_dao

    @override
    async def handle(self, command: ImportCatalogCommand) -> CatalogImportResponse:
        snapshot = command.snapshot
        batch_id = snapshot.batch_id
        dao = self._catalog_projection_dao

        prices = [
            price
            for price in snapshot.prices
            if price.amount > Decimal(0)
            and price.currency.strip().lower() in SUPPORTED_CURRENCIES
        ]
        discarded = len(snapshot.prices) - len(prices)
        accepted = 0

        if snapshot.categories:
            accepted += await dao.upsert_categories(snapshot.categories, batch_id)

        if snapshot.products:
            accepted += await dao.upsert_products(snapshot.products, batch_id)

        if snapshot.price_types:
            accepted += await dao.upsert_price_types(snapshot.price_types, batch_id)

        if prices:
            accepted += await dao.upsert_prices(prices, batch_id)

        if snapshot.stock:
            accepted += await dao.upsert_stock(snapshot.stock, batch_id)

        if snapshot.price_type_bindings:
            accepted += await dao.upsert_price_type_bindings(
                snapshot.price_type_bindings,
                batch_id,
            )

        scope = describe_scope(snapshot.scope)
        logger.info(
            "import_catalog: batch=%s scope=%s accepted=%d discarded=%d",
            batch_id,
            scope,
            accepted,
            discarded,
        )

        return CatalogImportResponse(
            batch_id=batch_id,
            scope=scope,
            accepted=accepted,
            discarded=discarded,
        )
