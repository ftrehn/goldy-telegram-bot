import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, final

from goldy.application.common.ports.site import SitePriceRequest, SitePricing
from goldy.application.common.ports.users import SiteLinkQueryGateway
from goldy.application.error import SiteCustomerNotLinkedError
from goldy.domain.catalog.values.price_type_id import PriceTypeId
from goldy.domain.catalog.values.product_id import ProductId
from goldy.domain.common.values.money import Money
from goldy.domain.common.values.quantity import Quantity
from goldy.domain.users.values.user_id import UserId

logger: Final[logging.Logger] = logging.getLogger(__name__)

PERSONAL_PRICE_TYPE_ID: Final[PriceTypeId] = PriceTypeId(value="PERSONAL")
"""The price list an order records when the site priced it for the customer.

Not a price type the site exports — there is no such list anywhere. It says
on the order that the prices came from the customer's own terms on the site
(company discount, contract prices, min(BASE, OPT)) rather than from the
guest catalog, which is the one thing a manager reading the order needs to
know about where its numbers came from.
"""


@final
@dataclass(frozen=True, slots=True)
class PersonalPrices:
    """The site's prices for one linked customer.

    ``prices`` holds every requested product; ``None`` means the site will
    not sell that product to this customer — hidden, archived, unpriced.
    """

    prices: Mapping[ProductId, Money | None]

    def price_of(self, product_id: ProductId) -> Money | None:
        return self.prices.get(product_id)


@final
class PersonalPricingService:
    """Asks the site for a linked customer's prices, and nobody else's.

    Whether to ask at all is read from the bot's copy of the link, so a retail
    customer's cart never waits on the site. A link the site has forgotten —
    the customer unlinked in the cabinet — reads as no link: the person sees
    the guest prices, which is exactly what the site would now charge them.

    An outage is not swallowed here. Showing a wholesale customer retail
    prices without saying so, or placing their order at retail, would be the
    quiet kind of wrong; the callers decide what to say instead.
    """

    def __init__(
        self,
        site_link_query_gateway: SiteLinkQueryGateway,
        site_pricing: SitePricing,
    ) -> None:
        self._site_link_query_gateway: Final[SiteLinkQueryGateway] = (
            site_link_query_gateway
        )
        self._site_pricing: Final[SitePricing] = site_pricing

    async def is_linked(self, user_id: UserId) -> bool:
        return await self._site_link_query_gateway.read_for(user_id) is not None

    async def for_user(
        self,
        user_id: UserId,
        items: Sequence[tuple[ProductId, Quantity]],
    ) -> PersonalPrices | None:
        """The site's prices for these items, or ``None`` for a guest.

        Raises:
            SiteUnavailableError: the person is linked and the site did not
                answer.
        """
        if not await self.is_linked(user_id):
            return None

        if not items:
            return PersonalPrices(prices={})

        try:
            answered = await self._site_pricing.prices_for(
                str(user_id),
                [SitePriceRequest(product_id=pid, quantity=qty) for pid, qty in items],
            )
        except SiteCustomerNotLinkedError:
            logger.info(
                "pricing: the site no longer links %s, pricing as a guest", user_id
            )
            return None

        prices: dict[ProductId, Money | None] = dict.fromkeys(
            (product_id for product_id, _ in items),
            None,
        )
        prices.update({price.product_id: price.unit_price for price in answered})
        return PersonalPrices(prices=prices)
