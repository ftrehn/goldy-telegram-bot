from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.priced_product import PricedProduct
from goldy.domain.catalog.values.product_id import ProductId

if TYPE_CHECKING:
    from goldy.domain.users.values.user_id import UserId


@dataclass(frozen=True, slots=True)
class ResolvedPriceType:
    """The price list a customer buys at, resolved in one query.

    Deliberately narrow. The binding is keyed by phone number in the
    projection and falls back to the price type configured for the bot, so by
    the time this is built the question "which price list" is already answered
    and only two facts are left to carry.

    ``is_supported`` is false when 1C sent a currency this service does not
    know. Handing back the default price list instead would show that customer
    somebody else's prices without telling them, so the resolver turns this
    flag into a refusal rather than a fallback.

    Not a view. Nothing here is on its way to a screen — it is read with the
    intent to put a price type on an order, which is why the id is already a
    domain value and why the reader lives beside the write side.
    """

    price_type_id: PriceTypeId
    is_supported: bool


@dataclass(frozen=True, slots=True)
class CartPrices:
    """What the catalog prices out of a cart, and what it does not.

    ``priced_products`` are finished domain values — every one of them has a
    price — and ``unpriced_product_ids`` are the products the catalog still
    holds but has no row for under this price list. The two are kept apart
    rather than folded into one list with an optional price, because a
    "priced product without a price" is a contradiction the checkout would
    have to remember to check for on every line. A product absent from both
    is gone from the catalog altogether, which ``CheckoutService`` reports
    against the line it happened on.
    """

    priced_products: Sequence[PricedProduct]
    unpriced_product_ids: Sequence[ProductId]


class PricingReader(Protocol):
    """Reads the same prices as the storefront, with the intent to keep them.

    A reader beside ``CatalogQueryGateway`` rather than two more methods on
    it, and the name says which side of the line it stands on: it hands back
    domain values, never views. **Nothing behind this port may be cached,
    ever.** A stale price on a storefront page is cosmetic; a stale price
    copied into an order line is a wrong total on a document somebody will be
    invoiced against. The precedent is ``OutboxCommandGateway.read_pending``,
    which lives on the write side for the same kind of reason.

    The primitives the projection stores become validated domain values on the
    way out of the adapter, the way the type decorators already build them for
    the command gateways. The application therefore never sees a product name
    it would have to validate itself, and never receives a view it would have
    to turn back into a value.

    The configured default price type reaches the adapter through its
    constructor, already parsed, the way ``StaticAdminRegistry`` receives
    parsed phone numbers. Neither this port nor any application service reads a
    setting.
    """

    @abstractmethod
    async def read_price_type_for(self, user_id: UserId) -> ResolvedPriceType | None:
        """The price list this customer buys at, in one query.

        Joins the person's phone number against the bindings in the projection
        and falls back to the price type configured for the bot when there is
        no binding, so "which price list" is already settled by the time this
        returns.

        Returns ``None`` when the projection holds neither — a broken snapshot
        rather than an ordinary absence. The resolver turns that, and an
        unsupported currency, into the two errors that say so.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_cart_prices(
        self,
        product_ids: Sequence[ProductId],
        price_type_id: PriceTypeId,
    ) -> CartPrices:
        """Everything an order line needs to be built, for these products.

        Every product the catalog still holds comes back on one side or the
        other: priced, or named among the unpriced. A product on neither side
        is gone from the catalog.

        Raises:
            DomainFieldError: the projection holds a value the domain refuses —
                an empty name, a nonsensical price. The projection is written
                without building values, so this is where a broken import is
                caught before it becomes a snapshot on an order.
        """
        raise NotImplementedError
