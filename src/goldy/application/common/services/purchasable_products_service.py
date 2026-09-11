from collections.abc import Sequence
from typing import Final, final

from goldy.application.common.ports.catalog import PricingGateway
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.domain.catalog.values.product_id import ProductId


@final
class PurchasableProductsService:
    """Narrows a list of products to the ones this customer can order today.

    Asked by "repeat this order", where the products come out of a snapshot
    taken months ago and three different things may have happened to each of
    them since: the import dropped it, the sweep deactivated it, or this
    customer's price list stopped covering it. All three mean one thing to a
    cart line — it cannot be ordered — so one question is asked and one answer
    comes back.

    Reads through :class:`PricingGateway` rather than ``CatalogQueryGateway``,
    and the difference between those two ports is exactly this question.
    ``read_existing_product_ids`` answers "is it still in the catalog" and
    knows nothing about price lists, and a caching decorator over it would be
    welcome; the pricing port applies the same ``is_active`` predicate, resolves
    the price in the same query, and is forbidden to be cached. ADR-0003 asks a
    repeat to check what the product costs *now*, and a cached answer to that
    is the stale copy the whole ADR is written against.

    A service rather than two collaborators of the handler, for the reason
    ``CartPricingService`` is one: resolving a price type and reading prices are
    two dependencies for a single question, and a handler that also loads a
    user, an order and a cart has no room for both.
    """

    def __init__(
        self,
        price_type_provider: PriceTypeProvider,
        pricing_gateway: PricingGateway,
    ) -> None:
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._pricing_gateway: Final[PricingGateway] = pricing_gateway

    async def among(self, product_ids: Sequence[ProductId]) -> frozenset[ProductId]:
        """Which of these the customer's own price list can sell them now.

        A set rather than the priced rows, because the one caller puts products
        into a cart and a cart holds no prices. Handing over prices nothing
        stores would invite somebody to store them.

        An empty request is answered without a query and without resolving a
        price type. A caller that filtered its lines first may well arrive with
        none, and refusing it with ``PriceTypeNotConfiguredError`` would be an
        error raised about nothing.

        Raises:
            PriceTypeNotConfiguredError: no price list resolves for this person.
            UnsupportedPriceTypeError: their price list is denominated in a
                currency this shop cannot price in.
        """
        if not product_ids:
            return frozenset()

        price_type_id = await self._price_type_provider.current()
        views = await self._pricing_gateway.read_priced_products(
            product_ids,
            price_type_id,
        )

        return frozenset(
            ProductId(value=view.product_id)
            for view in views
            if view.unit_price is not None
        )
