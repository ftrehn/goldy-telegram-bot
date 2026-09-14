from typing import Final, override

from goldy.application.common.mediator.handlers import QueryHandler
from goldy.application.common.ports.catalog import CatalogQueryGateway
from goldy.application.common.ports.identity_provider import IdentityProvider
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
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

    The price list is resolved for the person the identity provider names,
    in two visible steps: who is asking, then what they pay. The middleware
    put the account behind the update into the identity provider, and the
    resolver joins that person's phone number against the bindings 1C
    exported — there is no other context the price could come from.
    """

    def __init__(
        self,
        identity_provider: IdentityProvider,
        price_type_resolver: PriceTypeResolver,
        catalog_query_gateway: CatalogQueryGateway,
    ) -> None:
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._price_type_resolver: Final[PriceTypeResolver] = price_type_resolver
        self._catalog_query_gateway: Final[CatalogQueryGateway] = catalog_query_gateway

    @override
    async def handle(self, query: GetProductQuery) -> ProductView:
        user_id = await self._identity_provider.get_current_user_id()
        price_type_id = await self._price_type_resolver.resolve_for(user_id)
        product_id = ProductId(value=query.product_id)
        view = await self._catalog_query_gateway.read_product(product_id, price_type_id)

        if view is None:
            msg = f"Product '{product_id}' does not exist."
            raise ProductNotFoundError(msg)

        return view
