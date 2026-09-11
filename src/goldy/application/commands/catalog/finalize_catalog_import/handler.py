import logging
from typing import Final, override

from goldy.application.commands.catalog.finalize_catalog_import.command import (
    FinalizeCatalogImportCommand,
)
from goldy.application.commands.catalog.scope_description import describe_scope
from goldy.application.common.mediator.handlers import CommandHandler
from goldy.application.common.ports.catalog import (
    CatalogProjectionGateway,
    CatalogScopeKind,
)
from goldy.application.common.views.catalog import CatalogFinalizationResponse
from goldy.application.error import CatalogSnapshotError
from goldy.domain.catalog.values.price_type_id import PriceTypeId

logger: Final[logging.Logger] = logging.getLogger(__name__)


class FinalizeCatalogImportHandler(
    CommandHandler[FinalizeCatalogImportCommand, CatalogFinalizationResponse],
):
    """Sweeps one scope clean of everything the batch did not mention.

    What "sweeps" means is the gateway's business and differs by scope, which
    is the one thing about this command that must not be confused: products and
    categories are deactivated and kept forever because placed orders point at
    them, while prices and stock are deleted, since a price withdrawn in 1C
    that survives in the projection is a price the shop does not offer.

    After a sweep over price types, the price list configured as the default is
    checked for. Its absence is a broken snapshot and not a customer's problem
    — without it, whoever has no binding has no prices at all — so the refusal
    goes to whoever ran the import. Raising here rolls the sweep back with the
    transaction, which is the point: a projection that lost its default price
    list is worse than one that kept a few stale rows.

    The check is asked only of that scope, deliberately. It is the only sweep
    that can remove a price type, and asking it of every finalisation would
    make a stock import fail for a reason that has nothing to do with stock,
    purely because the price lists had not been exported yet.

    The default reaches the constructor already parsed, as
    ``StaticAdminRegistry`` receives phone numbers: an application handler that
    read a setting would make the composition root its dependency.
    """

    def __init__(
        self,
        catalog_projection_gateway: CatalogProjectionGateway,
        default_price_type_id: PriceTypeId,
    ) -> None:
        self._catalog_projection_gateway: Final[CatalogProjectionGateway] = (
            catalog_projection_gateway
        )
        self._default_price_type_id: Final[PriceTypeId] = default_price_type_id

    @override
    async def handle(
        self,
        command: FinalizeCatalogImportCommand,
    ) -> CatalogFinalizationResponse:
        gateway = self._catalog_projection_gateway
        swept = await gateway.finalize(command.scope, command.batch_id)

        if command.scope.kind is CatalogScopeKind.PRICE_TYPES:
            await self._ensure_default_price_type_survived()

        scope = describe_scope(command.scope)
        logger.info(
            "finalize_catalog_import: batch=%s scope=%s swept=%d",
            command.batch_id,
            scope,
            swept,
        )

        return CatalogFinalizationResponse(
            batch_id=command.batch_id,
            scope=scope,
            swept=swept,
        )

    async def _ensure_default_price_type_survived(self) -> None:
        """Refuses an import that left the projection without its default.

        Raises:
            CatalogSnapshotError: the configured default price type is not in
                the projection now that this batch has been swept.
        """
        present = await self._catalog_projection_gateway.has_price_type(
            self._default_price_type_id,
        )

        if not present:
            msg = (
                f"Default price type '{self._default_price_type_id}' is not "
                f"present in the catalog projection after the import."
            )
            raise CatalogSnapshotError(msg)
