from dataclasses import dataclass
from typing import Final, final

from goldy.application.common.ports.catalog import PricingGateway
from goldy.application.common.services.price_type_provider import PriceTypeProvider
from goldy.application.common.views.catalog import PricedProductView
from goldy.application.common.views.money import MoneyView
from goldy.application.error import ProductNotPricedError, UnsupportedPriceTypeError
from goldy.domain.carts.entities.cart import Cart
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.catalog.values.product_name import ProductName
from goldy.domain.catalog.values.sku import Sku
from goldy.domain.catalog.values.unit_of_measure import UnitOfMeasure
from goldy.domain.common.values.currency import Currency
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
    priced_products: tuple[PricedProduct, ...]

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
    by dishka — so the price type provider and the pricing gateway move behind
    this service together. It is the same move ``UserProvider`` makes.

    It is also the answer to "who turns the read model into domain values".
    Primitives out of the projection become a validated :class:`PricedProduct`
    here and nowhere else, which is what stops an empty name or a nonsensical
    price from reaching an order line and being kept there as a snapshot.
    """

    def __init__(
        self,
        price_type_provider: PriceTypeProvider,
        pricing_gateway: PricingGateway,
    ) -> None:
        self._price_type_provider: Final[PriceTypeProvider] = price_type_provider
        self._pricing_gateway: Final[PricingGateway] = pricing_gateway

    async def for_cart(self, cart: Cart) -> CartPricing:
        """Reads the current price of everything in the cart.

        Read fresh on every call and never from a cache: these prices are about
        to be copied into an order, and a stale number there is a wrong total
        on a document somebody will be invoiced against.

        Products missing from the answer are left missing rather than refused
        here. They mean the catalog lost the product, which ``CheckoutService``
        reports against the line it happened on.

        Raises:
            PriceTypeNotConfiguredError: no price list resolves for this person.
            UnsupportedPriceTypeError: their price list, or one of the prices
                in it, is in a currency this shop cannot handle.
            ProductNotPricedError: the catalog still has the product but has no
                price for it under this price list.
        """
        price_type_id = await self._price_type_provider.current()
        views = await self._pricing_gateway.read_priced_products(
            [line.product_id for line in cart.lines],
            price_type_id,
        )

        return CartPricing(
            price_type_id=price_type_id,
            priced_products=tuple(self._to_priced_product(view) for view in views),
        )

    def _to_priced_product(self, view: PricedProductView) -> PricedProduct:
        """The boundary: primitives in, validated domain values out.

        Raises:
            ProductNotPricedError: the storefront shows this product as "price
                on request", which is a fine state to browse in and an
                impossible one to order from.
            UnsupportedPriceTypeError: the price is in an unknown currency.
        """
        if view.unit_price is None:
            msg = (
                f"Product '{view.product_id}' has no price under this price "
                f"type and cannot be ordered."
            )
            raise ProductNotPricedError(msg)

        return PricedProduct(
            product_id=ProductId(value=view.product_id),
            sku=None if view.sku is None else Sku(value=view.sku),
            name=ProductName(value=view.name),
            unit=UnitOfMeasure(view.unit_id, view.unit_name),
            unit_price=Money(view.unit_price.amount, _currency_of(view.unit_price)),
        )


def _currency_of(unit_price: MoneyView) -> Currency:
    """Reads the currency of a price the projection stored as text.

    1C spells currency codes in upper case and our enum in lower, so the
    comparison is made on one of them rather than on whichever the exchange
    happened to send.

    Raises:
        UnsupportedPriceTypeError: the code names a currency this shop cannot
            price in. The import marks such price types unsupported and the
            price type provider refuses them earlier, so reaching this means
            the projection disagrees with itself — still a refusal, never a
            silent substitution of a currency we do like.
    """
    try:
        return Currency(unit_price.currency.strip().lower())
    except ValueError as error:
        msg = f"Currency '{unit_price.currency}' is not one this shop prices in."
        raise UnsupportedPriceTypeError(msg) from error
