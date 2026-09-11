from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.views.catalog import ProductView
from goldy.application.error import ProductNotFoundError
from goldy.application.queries.catalog.get_product.query import GetProductQuery
from goldy.domain.catalog.values.product_id import ProductId


class GetProductHandler(QueryHandler[GetProductQuery, ProductView]):
    """Reads one card, refusing plainly when the catalog no longer holds it.

    A missing product is an error rather than an empty card because the card is
    reached from a button: something was listed a moment ago and an import
    swept it in between, and the honest answer is to say so and send the
    customer back to the listing.

    A card with no price is **not** an error. There may be no row under this
    customer's price list, which the card renders as "price on request" — the
    difference between "we do not sell this" and "the price is not on file" is
    a difference the customer can act on.
    """

    def __init__(
        self,
        price_type_provider: PriceTypeProvider,
        catalog_query_gateway: CatalogQueryGateway,
    ) -> None:
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway

    @override
    async def handle(self, query: GetProductQuery) -> ProductView:
        price_type_id = await self._price_type_provider.current()
        product_id = ProductId(value=query.product_id)
        view = await self._catalog_query_gateway.read_product(product_id, price_type_id)

        if view is None:
            msg = f"Product '{product_id}' does not exist."
            raise ProductNotFoundError(msg)

        return view
