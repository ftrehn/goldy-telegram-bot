from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from goldy.application.common.views.catalog import PriceTypeView, PricedProductView
    from goldy.domain.catalog.values.price_type_id import PriceTypeId
    from goldy.domain.catalog.values.product_id import ProductId
    from goldy.domain.users.values.user_id import UserId


class PricingGateway(Protocol):
    """Reads the same prices as the storefront, with the intent to keep them.

    **Nothing behind this port may be cached, ever.** A stale price on a
    storefront page is cosmetic; a stale price copied into an order line is a
    wrong total on a document somebody will be invoiced against. That is the
    whole reason this is a second port over the same tables rather than two
    methods on :class:`CatalogQueryGateway`, where a caching decorator would be
    welcome — the precedent is ``OutboxCommandGateway.read_pending``, which
    lives on the write side for the same kind of reason.

    The configured default price type reaches the adapter through its
    constructor, already parsed, the way ``StaticAdminRegistry`` receives
    parsed phone numbers. Neither this port nor any application service reads a
    setting.
    """

    @abstractmethod
    async def read_price_type_for(self, user_id: UserId) -> PriceTypeView | None:
        """The price list this customer buys at, in one query.

        Joins the person's phone number against the bindings in the projection
        and falls back to the price type configured for the bot when there is
        no binding, so "which price list" is already settled by the time this
        returns.

        Returns ``None`` when the projection holds neither — a broken snapshot
        rather than an ordinary absence. The application service turns that,
        and an unsupported currency, into the two errors that say so.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_priced_products(
        self,
        product_ids: Sequence[ProductId],
        price_type_id: PriceTypeId,
    ) -> Sequence[PricedProductView]:
        """Everything an order line needs to be built, for these products.

        A row comes back for every product that still exists, priced or not:
        the two absences mean different things and are refused with different
        errors. A product missing from the result entirely is gone from the
        catalog; a product present with no price has no row under this price
        list.
        """
        raise NotImplementedError
