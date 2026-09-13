from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, final

from goldy.application.common.ports.catalog import PricingReader
from goldy.application.common.services.price_type_resolver import PriceTypeResolver
from goldy.application.error import ProductNotPricedError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.common.values.money import Money


@final
@dataclass(frozen=True, slots=True)
class CartPricing:
    """A cart priced for one customer: the price list, and what it costs.

    Both halves travel together because both end up on the order — the price
    type as a mandatory field of :class:`Order`, the products as the snapshot
    in its lines — and reading them apart would let a snapshot be taken at one
    price list while the order records another.
    """

    price_type_id: PriceTypeId
    priced_products: Sequence[PricedProduct]

    def total_for(self, cart: Cart) -> Money | None:
        """What this cart comes to at these prices, or nothing if it cannot be.

        ``None`` rather than an error, and the distinction matters at exactly
        one call site. A line whose product has vanished from the catalog
        entirely is not a repricing, and ``CheckoutService`` names that failure
        precisely with ``UnpricedCartLineError``; a total summed over the lines
        that survived would be compared against the screen, differ, and refuse
        the order first with the wrong message. An empty cart has no total for
        the same reason it has no currency — there is nothing to take one from.
        """
        prices = {priced.product_id: priced for priced in self.priced_products}
        total: Money | None = None

        for line in cart.lines:
            priced = prices.get(line.product_id)

            if priced is None:
                return None

            line_total = priced.unit_price.times(line.quantity)
            total = line_total if total is None else total + line_total

        return total


@final
class CartPricingService:
    """Prices a whole cart at the customer's own price list, in one call.

    Exists to collapse two collaborators into one. ``PlaceOrderHandler``
    described naively needs seven, ``PLR0913`` allows five, ``# noqa`` is
    forbidden and a parameter object does not work for a constructor injected
    by dishka — so the price type resolver and the pricing reader move behind
    this service together. It is the same move ``UserProvider`` makes.

    Nothing is converted here. The reader hands back domain values, built at
    the boundary of the projection the way the type decorators build them for
    every command gateway, so this service has one job: ask for the price
    list of the cart's owner, ask for the prices, and refuse a cart the
    catalog lists but does not price.
    """

    def __init__(
        self,
        price_type_resolver: PriceTypeResolver,
        pricing_reader: PricingReader,
    ) -> None:
        self._price_type_resolver: Final[PriceTypeResolver] = price_type_resolver
        self._pricing_reader: Final[PricingReader] = pricing_reader

    async def for_cart(self, cart: Cart) -> CartPricing:
        """Reads the current price of everything in the cart, for its owner.

        Read fresh on every call and never from a cache: these prices are about
        to be copied into an order, and a stale number there is a wrong total
        on a document somebody will be invoiced against.

        Products missing from the answer are left missing rather than refused
        here. They mean the catalog lost the product, which ``CheckoutService``
        reports against the line it happened on.

        Raises:
            PriceTypeNotConfiguredError: no price list resolves for this person.
            UnsupportedPriceTypeError: their price list is in a currency this
                shop cannot handle.
            ProductNotPricedError: the catalog still has a product but has no
                price for it under this price list — the storefront shows it
                as "price on request", which is a fine state to browse in and
                an impossible one to order from.
        """
        price_type_id = await self._price_type_resolver.resolve_for(cart.user_id)
        prices = await self._pricing_reader.read_cart_prices(
            [line.product_id for line in cart.lines],
            price_type_id,
        )

        if prices.unpriced_product_ids:
            named = ", ".join(str(item) for item in prices.unpriced_product_ids)
            msg = f"Products have no price under this price type: {named}."
            raise ProductNotPricedError(msg)

        return CartPricing(
            price_type_id=price_type_id,
            priced_products=prices.priced_products,
        )
